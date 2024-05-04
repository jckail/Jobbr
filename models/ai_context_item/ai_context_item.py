from db import saveDataModel
from sqlmodel import SQLModel, Field, Column, String
from models.mixins import BaseMixin

from uuid import UUID
from typing import Optional, List

from sqlalchemy.dialects import postgresql
from ..enums import SourceType


class AI_Context_Item(BaseMixin, SQLModel, table=True):
    """
    id the uuid of the record
    file_source the source file of the role
    url : the orignal URL from the previous call
    """

    id: UUID = Field(primary_key=True)
    context_owner_id: UUID  # can be an ai, user, context, or function
    source_name: str
    source_type: SourceType
    source_owner_id: Optional[UUID]
    description: Optional[str]  # description of context
    alias: Optional[str]
    # data: str  # TODO this could become a UII risk this will be whatever is loaded # Eventually store this as a hash
    estimated_tokens: Optional[int]
    authorized_users: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )

    extra_data: Optional[dict] = Field(default=None, sa_column=Column(postgresql.JSONB))

    def saveModel(self):
        saveDataModel(self)

    ## delete statment for save if exists
