from sqlmodel import SQLModel
from models.mixins import BaseMixin
from ..enums import GenreURLChoices
from pydantic import validate_call


class BandBase(BaseMixin, SQLModel):
    name: str
    genre: GenreURLChoices

    @validate_call
    def title_case_genre(cls, genre: GenreURLChoices | str) -> str:
        if isinstance(genre, str):
            return genre.title()
        elif isinstance(genre, GenreURLChoices):
            return genre.value.title()
