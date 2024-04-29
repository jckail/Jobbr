import uuid
from sqlmodel import Field, Relationship
from .bandBase import BandBase
from ..album.album import Album
from datetime import date


class Band(BandBase, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True
    )  # backpopulates u
    album: list[Album] = Relationship(back_populates="band")
    date_formed: date | None
