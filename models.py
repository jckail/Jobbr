from datetime import date, datetime
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship
from mixins import Timestamp
from fastapi import HTTPException

from pydantic import validate_call, validator  # Import this instead


class GenreURLChoices(Enum):
    ROCK = "rock"
    ELECTRONIC = "electronic"
    METAL = "metal"
    HIP_HOP = "hip-hop"


class GenreChoices(Enum):
    ROCK = "Rock"
    ELECTRONIC = "Electronic"
    METAL = "Metal"
    HIP_HOP = "Hip-Hop"


class AlbumBase(Timestamp, SQLModel):
    title: str
    release_date: date
    band_id: int | None = Field(default=None, foreign_key="band.id")

    @validator(
        "release_date", pre=True, always=True
    )  # `pre=True` to catch it before any other processing
    def validate_release_date(cls, v):
        try:
            # Convert string to date object and return it
            return datetime.strptime(v, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=422,
                detail=[
                    {
                        "type": "date",
                        "loc": [
                            "body",
                            "release_date",
                        ],
                        "msg": "must be a date or a string in YYYY-MM-DD format IE 2024-01-01",
                        "input": v,
                        "ctx": "must be a date or a string in YYYY-MM-DD format IE 2024-01-01",
                    }
                ],
            )


class Album(AlbumBase, table=True):
    id: int = Field(default=None, primary_key=True)
    band: "Band" = Relationship(back_populates="albums")


class BandBase(Timestamp, SQLModel):
    name: str
    genre: GenreURLChoices


class BandCreate(BandBase):
    albums: list[Album] | None = None

    @validate_call  # Use this decorator before the method
    def title_case_genre(cls, genre: GenreChoices | str) -> str:
        if isinstance(genre, str):
            return genre.title()
        elif isinstance(genre, GenreChoices):
            return genre.value.title()


class Band(BandBase, table=True):
    id: int = Field(default=None, primary_key=True)
    albums: list[Album] = Relationship(back_populates="band")
