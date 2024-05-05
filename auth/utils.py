import os
import jwt
import http.client
import json
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional, List, Dict


class ApiResponse(BaseModel):
    success: bool
    message: str
    data: dict


load_dotenv()


class AuthToken(BaseModel):
    access_token: str
    scope: str
    expires_in: int
    token_type: str


class Auth0Token(BaseModel):
    """Does all the token verification using PyJWT"""

    jwt_access_token: str
    permissions: Optional[List[str]] = None
    scopes: Optional[List[str]] = None

    # These are environment-dependent and should be obtained outside of the Pydantic model,
    # or default values can be used directly within the model definition.
    auth0_domain: str = os.getenv("AUTH0_DOMAIN")
    auth0_issuer_url: str = f"https://{auth0_domain}/"
    auth0_audience: str = os.getenv("AUTH0_AUDIENCE")
    algorithm: str = "RS256"
    jwks_uri: str = f"https://{auth0_domain}/.well-known/jwks.json"
    payload: Optional[Dict] = None

    def verify(self):
        # This gets the 'kid' from the passed token
        try:
            jwks_client = jwt.PyJWKClient(self.jwks_uri)
            signing_key = jwks_client.get_signing_key_from_jwt(
                self.jwt_access_token
            ).key
        except jwt.exceptions.PyJWKClientError as error:
            return {"status": "error", "msg": error.__str__()}
        except jwt.exceptions.DecodeError as error:
            return {"status": "error", "msg": error.__str__()}

        try:
            payload = jwt.decode(
                self.jwt_access_token,
                signing_key,
                algorithms=self.algorithm,
                audience=self.auth0_audience,
                issuer=self.auth0_issuer_url,
            )
        except Exception as e:
            return {"status": "error", "message": str(e)}

        if self.scopes:
            result = self._check_claims(payload, "scope", str, self.scopes.split(" "))
            if result.get("error"):
                return result

        if self.permissions:
            result = self._check_claims(payload, "permissions", list, self.permissions)
            if result.get("error"):
                return result

        return payload

    def _check_claims(self, payload, claim_name, claim_type, expected_value):

        instance_check = isinstance(payload[claim_name], claim_type)
        result = {"status": "success", "status_code": 200}

        payload_claim = payload[claim_name]

        if claim_name not in payload or not instance_check:
            result["status"] = "error"
            result["status_code"] = 400

            result["code"] = f"missing_{claim_name}"
            result["msg"] = f"No claim '{claim_name}' found in token."
            return result

        if claim_name == "scope":
            payload_claim = payload[claim_name].split(" ")

        for value in expected_value:
            if value not in payload_claim:
                result["status"] = "error"
                result["status_code"] = 403

                result["code"] = f"insufficient_{claim_name}"
                result["msg"] = (
                    f"Insufficient {claim_name} ({value}). You don't have "
                    "access to this resource"
                )
                return result
        return result


# def generateToken(permissions=None, scopes=None, payload=None):

#     token = None
#     res = None

#     try:
#         conn = http.client.HTTPSConnection(str(os.getenv("AUTH0_DOMAIN")))
#         # Correctly formatted payload string with placeholders
#         # payload = '{{"client_id":"{client_id}","client_secret":"{client_secret}","audience":"{audience}","grant_type":"client_credentials","permissions":"{permissions}"}}'
#         # payload = payload.format(
#         #     client_id=os.getenv("AUTH0_CLIENT_ID"),
#         #     client_secret=os.getenv("AUTH0_CLIENT_SECRET"),
#         #     audience=str(os.getenv("AUTH0_AUDIENCE")),
#         #     permissions=permissions,
#         #     payload=payload,
#         # )
#         payload = {
#             "client_id": os.getenv("AUTH0_CLIENT_ID"),
#             "client_secret": os.getenv("AUTH0_CLIENT_SECRET"),
#             "audience": str(os.getenv("AUTH0_AUDIENCE")),
#             "grant_type": "client_credentials",
#         }

#         # todo add in scopes, permissions, and user
#         headers = {"content-type": "application/json"}
#         conn.request("POST", "/oauth/token", payload, headers)
#         res = conn.getresponse()


#         if res.status == 200:
#             data = res.read()
#             token = data.decode("utf-8")
#             return res.status, token
#         else:
#             return None
#     except Exception as e:
#         raise e


def generateToken(permissions=None, scopes=None):
    try:
        conn = http.client.HTTPSConnection(os.getenv("AUTH0_DOMAIN"))
        payload = {
            "client_id": os.getenv("AUTH0_CLIENT_ID"),
            "client_secret": os.getenv("AUTH0_CLIENT_SECRET"),
            "audience": os.getenv("AUTH0_AUDIENCE"),
            "grant_type": "client_credentials",
        }

        # Include permissions and scopes if provided
        if permissions:
            payload["permissions"] = permissions
        if scopes:
            payload["scope"] = " ".join(
                scopes
            )  # Assuming scopes are to be space-separated

        headers = {"Content-Type": "application/json"}
        payload_json = json.dumps(payload)
        conn.request("POST", "/oauth/token", payload_json, headers)
        res = conn.getresponse()
        if res.status == 200:
            data_dict = json.loads(res.read())
            return AuthToken(**data_dict)
        else:
            return res
    except Exception as e:
        raise e
