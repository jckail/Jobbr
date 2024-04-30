from sqlmodel import SQLModel, Field, AutoString
from pydantic import HttpUrl
from models.mixins import BaseMixin


class URLBase(BaseMixin, SQLModel):
    url: str
