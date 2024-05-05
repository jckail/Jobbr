from fastapi import Depends, Response, status

from fastapi.security import HTTPBearer
from numpy import result_type

from auth.utils import Auth0Token, generateToken

import fastapi

from db import get_session


tags_metadata = ["auth"]
router = fastapi.APIRouter(tags=tags_metadata)

token_auth_scheme = HTTPBearer()


@router.get("/api/private")
def privateExample(response: Response, token: str = Depends(token_auth_scheme)):
    """A valid access token is required to access this route"""

    result = Auth0Token(jwt_access_token=token.credentials).verify()

    if result.get("status"):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return result

    return result


@router.post("/api/privateGen")  ## add userid to path
def privateGen(permissions=None, scopes=None, token: str = Depends(token_auth_scheme)):
    """A valid access token is required to access this route"""

    result = Auth0Token(jwt_access_token=token.credentials).verify()

    if result.get("status"):
        # return unauthenticated
        return status.HTTP_403_FORBIDDEN

    return generateToken(permissions, scopes)

    # # if result.get("status"):
    # #     status= status.HTTP_400_BAD_REQUEST
    # #     return result

    # return {"response": status, "result": token}
