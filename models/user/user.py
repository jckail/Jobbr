import uuid
from sqlmodel import Field, Relationship
from .userBase import UserBase


class User(UserBase, table=True):

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True
    )  # backpopulates u
    hashed_password: str
