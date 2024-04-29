import uuid
from datetime import date
from sqlmodel import SQLModel, Field
from models.mixins import BaseMixin


class AlbumBase(BaseMixin, SQLModel):
    title: str
    release_date: date
    band_id: uuid.UUID | None = Field(default_factory=uuid.uuid4, foreign_key="band.id")
