import fastapi
from fastapi import HTTPException, status, Depends, Header, Request, Security
from fastapi.security import (
    APIKeyHeader,
    OAuth2PasswordBearer,
    HTTPBearer,
    OAuth2AuthorizationCodeBearer,
)
from jose import jwt, JWTError

from models import User, UserBase, TokenData, Token


from typing import List, Optional

SECRET_KEY = "e26da5723c636703177cf3f036cfab42efdf11d79f632a79cb40daacf6e006be"
## This is for example purposes, if deplyed in prod do not have this here.
ALGORITHM = "HS256"
tags_metadata = ["special"]
router = fastapi.APIRouter(tags=tags_metadata)


def api_key_validation(api_key, header_name: str, scopes: List[str]):
    """
    Validates the access token and checks if it has the required scope.

    Args:
        api_key (str): The access token to be validated.
        header_name (str): The name of the header containing the access token.
        scopes (List[str]): The list of required scopes.

    Raises:
        HTTPException: If the access token is invalid, doesn't have the required scope,
            or if there is an error during validation.

    Returns:
        dict: The decoded payload of the access token.

    """
    scope = "special"
    try:
        if not api_key:
            raise HTTPException(
                status_code=403, detail=f"api_key is None: api_key: {api_key}"
            )
        payload = jwt.decode(api_key, SECRET_KEY, algorithms=[ALGORITHM])
        if scopes != payload.get("scopes", ""):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Insufficient scope. requires {scope}",
            )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credential {e} {header_name}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid api_key header format {e}",
        )
    except AttributeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"api_key header must be provided {e}",
        )


async def secure_key(api_key: str = Header(None)):
    return api_key


async def get_api_key(
    api_key: str = Security(APIKeyHeader(name="api_key", auto_error=False))
):
    if api_key != "":
        return api_key
    else:
        raise HTTPException(
            status_code=403, detail="Could not fetch header credentials"
        )


@router.get("/protectedExample")
def main(
    api_key: Optional[str] = Security(secure_key),
    header_api_key: str = Security(get_api_key),
):
    required_scopes = ["special"]
    # authorization = request.headers.get("Authorization")
    api_key if api_key else header_api_key

    payload = api_key_validation(api_key, "magic", required_scopes)
    return payload
