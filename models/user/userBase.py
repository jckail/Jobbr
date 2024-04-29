from sqlmodel import SQLModel
from models.mixins import BaseMixin


class UserBase(BaseMixin, SQLModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None
