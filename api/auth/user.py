import fastapi
from fastapi import Depends, HTTPException, status, Header

from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from db import get_session
from models import User, UserBase, TokenData, Token
from typing import List


tags_metadata = ["auth"]
router = fastapi.APIRouter(tags=tags_metadata)


# we want to store the user as hashed AND the pw as hashed with 2 seperate keys?
SECRET_KEY = "e26da5723c636703177cf3f036cfab42efdf11d79f632a79cb40daacf6e006be"

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRES_MINUTES = 30


pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
## TODO you should be able to validate without token URL
##TODO change scopes to enums
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire, "scope": "login"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def authenticate_user(session, user_id, password: str):
    user = session.query(User).filter(User.id == user_id).first()

    if not user:
        return False

    if not verify_password(password, user.hashed_password):
        return False

    return user


async def get_current_token(token: str = Depends(oauth2_scheme)):
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="could not authenticate",
        headers={"WWW-Authenticate": "BEARER"},
    )
    try:

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        rs = "login"
        if rs not in payload.get("scope", ""):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Insufficient scope. requires {rs}",
            )
        user_id: str = payload.get("sub")

        if user_id is None:
            raise credential_exception

        token_data = TokenData(user_id=user_id)

    except JWTError:
        raise credential_exception

    return token_data


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    ##TODO: generate login event log this to table
    authError = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "BEARER"},
    )
    user = session.query(User).filter(User.username == form_data.username).first()
    if not user:
        raise authError
    if not verify_password(form_data.password, user.hashed_password):
        raise
    if not user:
        raise authError

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRES_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me/", response_model=User)
async def read_users_me(
    current_token: Token = Depends(get_current_token),
    session: Session = Depends(get_session),
):
    user = session.query(User).filter(User.id == current_token.user_id).first()
    # if user is None:
    #     raise credential_exception
    # return user
    return user


# @router.get("/users/me/items")
# async def read_own_items(current_user: UserBase = Depends(get_current_active_user)):
#     return [{"item_id": 1, "owner": current_user}]


@router.post("/register")
async def register_user(
    user: UserBase,
    password: str,
    session: Session = Depends(get_session),
):

    if session.query(User).filter(User.username == user.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User lready exists",
        )

    newUser = User(**user.dict(), hashed_password=get_password_hash(password))
    session.add(newUser)
    session.commit()
    session.refresh(newUser)

    return {"message": "User registered successfully"}


def generate_special_token(data: dict, scopes: List[str], expires_delta: int = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=15
        )  # Default to 15 minutes if not specified
    to_encode.update(
        {"exp": expire, "scopes": scopes}
    )  # Add scope to the token payload
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


##TODO: For all tokens other than login save these to a database to revoke all etc
@router.get("/special", response_model=Token)
async def genSpecial(
    scopes: List[str] = Header(["special"]),
    expire_time_minutes: int = Header(15),
    # default is 15 make this a look up to the scopes passed
    current_token: Token = Depends(get_current_token),
    session: Session = Depends(get_session),
):
    user = session.query(User).filter(User.id == current_token.user_id).first()

    # scopes = ["special"]
    # if scopesx:
    #     scopes = [scopesx]
    # expire_time_minutes = 5
    # if expire_time_minutesx:
    #     expire_time_minutes = expire_time_minutesx
    access_token = generate_special_token(
        data={"sub": str(user.id)}, scopes=scopes, expires_delta=expire_time_minutes
    )
    return {"access_token": access_token, "token_type": "access_token"}


# eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1MTFiZmIwYS1hZDBlLTQyYjItODI1OS1kMTVhMDcwNTFiNzciLCJleHAiOjE3MTQ0MDUzODUsInNjb3BlcyI6WyJzcGVjaWFsIl19.g2UcL8hZkIbgAxRX925sFWej8XHodCCPErGj-LxgwuQ
