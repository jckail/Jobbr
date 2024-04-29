import fastapi
from fastapi import HTTPException, status, Depends, Header, Request
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer, HTTPBearer
from jose import jwt, JWTError

from models import User, UserBase, TokenData, Token

tags_metadata = ["special"]
router = fastapi.APIRouter(tags=tags_metadata)

SECRET_KEY = "e26da5723c636703177cf3f036cfab42efdf11d79f632a79cb40daacf6e006be"
ALGORITHM = "HS256"


async def validate_token(access_token: str = Header(...)):
    """
    Validates the access token and checks if it has the required scope.

    Args:
        access_token (str): The access token to be validated.

    Raises:
        HTTPException: If the access token is invalid, doesn't have the required scope,
            or if there is an error during validation.

    Returns:
        dict: The decoded payload of the access token.

    """
    scope = "special"
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        if scope not in payload.get("scope", ""):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Insufficient scope. requires {scope}",
            )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credential {e}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid access_token header format {e}",
        )
    except AttributeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"access_token header must be provided {e}",
        )


@router.post("/helloworld/")
async def protected_endpoint(
    payload: dict = Depends(validate_token),
):
    """
    This endpoint is used to handle authorized requests.

    Parameters:
    - payload (dict): The payload containing the request data.

    Returns:
    - dict: A dictionary containing the response message.
    """
    # Check if the Authorization header is present and valid
    # data = validate_token(authtoken)
    # if data:
    #     # Extract the JSON body from the request
    #     # data = await request.json()
    #     return {"message": "Authorized access!", "your_data": data}
    # else:
    #     raise HTTPException(status_code=401, detail="Unauthorized")

    return {"hello": "world"}
