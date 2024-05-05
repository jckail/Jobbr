from fastapi import Depends, Response, status

from fastapi.security import HTTPBearer

from auth.utils import VerifyToken

import fastapi

from db import get_session


tags_metadata = ["auth"]
router = fastapi.APIRouter(tags=tags_metadata)

token_auth_scheme = HTTPBearer()


@router.get("/api/private")
def privateExample(response: Response, token: str = Depends(token_auth_scheme)):
    """A valid access token is required to access this route"""

    result = VerifyToken(token.credentials).verify()

    if result.get("status"):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return result

    return result
