from uuid import UUID, uuid4


from db import saveDataModel
from sqlmodel import (
    Field,
    Column,
    String,
)
from .stg_rolebase import Stg_RoleBase
from typing import Optional, List
from sqlalchemy.dialects import postgresql


class Stg_Role(Stg_RoleBase, table=True):
    """
    id the uuid of the record
    file_source the source file of the role
    url : the orignal URL from the previous call
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)  # backpopulates u
    app_ai_id: Optional[UUID]
    app_ai_event_id: Optional[UUID]
    specified_context_ids: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )
    context_id: Optional[UUID]  # this will probably break it
    extra_data: Optional[dict] = Field(
        default=None, sa_column=Column(postgresql.JSONB)
    )

    url_id: Optional[UUID]
    url: Optional[str]

    def saveModel(self):
        saveDataModel(self)
