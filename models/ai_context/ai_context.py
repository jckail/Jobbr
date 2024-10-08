from db import saveDataModel
from sqlmodel import SQLModel, Field, Column, String
from models.mixins import BaseMixin

from uuid import UUID
from typing import Optional, List

from sqlalchemy.dialects import postgresql


class AI_Context(BaseMixin, SQLModel, table=True):
    """
    id the uuid of the record
    file_source the source file of the role
    url : the orignal URL from the previous call
    """

    id: UUID = Field(primary_key=True)
    app_ai_id: UUID
    specified_context_ids: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )
    context_ids: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )  # this will probably break it
    extra_data: Optional[dict] = Field(default=None, sa_column=Column(postgresql.JSONB))

    def saveModel(self):
        saveDataModel(self)
