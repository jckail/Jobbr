from .bandBase import BandBase
from pydantic import validate_call
from ..album.album import Album
from datetime import date


class BandCreate(BandBase):
    album: list[Album] | None = None
    date_formed: date | None
