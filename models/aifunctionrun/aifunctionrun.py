from sqlmodel import Field
from uuid import UUID, uuid4


from .aifunctionrunbase import AIFunctionRunBase


class AIFunctionRun(AIFunctionRunBase, table=True):
    """
    id the uuid of the record
    file_source the source file of the role
    url : the orignal URL from the previous call
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)  # backpopulates u
    # add in query
