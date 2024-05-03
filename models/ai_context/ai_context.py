from uuid import UUID
from db import saveDataModel
from sqlmodel import SQLModel
from models import LLM

from sqlmodel import Field


from typing import Optional

from .app_ai_base import App_AI_Base


class App_AI(SQLModel, table=True):
    """ """

    app_ai_id: UUID = Field(primary_key=True)
    app_ai_id: UUID = Field(primary_key=True)
    model: LLM
    temperature: float  # the temerature of the model
    user_id: Optional[UUID] = None  # the creator of the ai
    ai_context_id: Optional[UUID] = None  ## the uuid of the context object created
    max_tokens: Optional[int]

    def saveModel(self):
        saveDataModel(self)


if __name__ == "__main__":
    aa = App_AI()
