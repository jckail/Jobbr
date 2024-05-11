from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os
import time

# Load environment variables
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

security = HTTPBearer()

def validate_token(http_auth: HTTPAuthorizationCredentials = Security(security)):
    try:
        token = http_auth.credentials
        payload  = jwt.decode(token,JWT_SECRET,do_verify=True,algorithms=[JWT_ALGORITHM],audience="authenticated",leeway=1)
        ##TODO add validation around the userid as well. this will be sent with the json
        if payload['exp'] < time.time():
            raise jwt.ExpiredSignatureError
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token is expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")