import uuid
from sqlmodel import SQLModel, Field, Relationship


class Token(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    access_token: str
    token_type: str


class TokenData(SQLModel):
    user_id: uuid.UUID | None = None
