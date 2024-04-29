import uuid
from datetime import datetime
from sqlmodel import Field, Relationship
from fastapi import HTTPException
from .albumBase import AlbumBase
from pydantic import validator


class Album(AlbumBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    band: "Band" = Relationship(back_populates="album")

    @validator("release_date", pre=True, always=True)
    def validate_release_date(cls, v):
        try:
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
