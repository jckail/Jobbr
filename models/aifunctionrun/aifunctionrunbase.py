from datetime import datetime

from sqlmodel import SQLModel, Field

from typing import Optional

from models.mixins import BaseMixin


##TODO create timer functions so that we can better see timing
## TODO test against langchain outputs etc its going to be better than this i think


class AIFunctionRunBase(BaseMixin, SQLModel):
    """
    id the uuid of the record
    file_source the source file of the role
    url : the orignal URL from the previous call
    """

    ## ADD IN PROMPT for user and system
    ## add in contexts and sources
    ## follow langchain terms
    input_model: str
    tokenCount: int
    function: str
    tries: int
    file_source: Optional[str]
    url: Optional[str]
    run_start_utc: int = Field(
        default_factory=lambda: int(datetime.now().timestamp()), nullable=False
    )
    # add in query
