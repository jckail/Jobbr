from uuid import UUID, uuid4

from models import (
    SourceType,
    AI_Context_Item,
)


from typing import Optional, List, Any
from helpers import load_file, download_from_supa_base


## will create a context ownership model


### context items are not bound to a particualr ai
class AI_CONTEXT_ITEM:
    def __init__(
        self,
        context_owner_id: UUID,  # owner of the context
        source_name: str,
        source_type: SourceType,
        source_id: Optional[UUID],
        description: str = None,
        alias: str = None,
        data: Any = None,
        estimated_tokens: int = None,
        authorized_users: List[
            str
        ] = None,  # list of users allowed to access the context
        extra_data: Optional[dict] = None,
    ):
        try:

            if not source_name:
                raise ValueError("source_name is required and cannot be empty.")

            if not hasattr(
                source_type, "name"
            ):  # Assuming source_type should have a 'name' attribute
                raise ValueError("Invalid source type provided.")

            self.context_owner_id = context_owner_id
            self.source_name = source_name
            # can be the name of an object alias OR name of a file
            self.source_type = source_type
            self.source_id = source_id
            self.description = description
            self.alias = alias if alias is not None else source_name
            self.data = data if data is not None else self.getContextData()
            self.estimated_tokens = estimated_tokens
            self.authorized_users = (
                authorized_users if authorized_users is not None else []
            )
            self.extra_data = extra_data if extra_data is not None else {}
            self.id = uuid4()
        except ValueError as e:
            print(f"Error initializing AI_CONTEXT_ITEM: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise
        self.save()

    def save(self):
        try:
            AI_Context_Item(
                id=self.id,
                context_owner_id=self.context_owner_id,
                source_name=self.source_name,
                source_type=self.source_type,
                source_id=self.source_id,
                description=self.description,
                alias=self.alias,
                estimated_tokens=self.estimated_tokens,
                authorized_users=self.authorized_users,
                extra_data=self.extra_data,
            ).saveModel()
        except Exception as e:
            print(f"Error saving AI_CONTEXT_ITEM: {e}")
            raise

    def getContextData(self):
        """
        # data is populated based on source type and source_name ie queries configs etc
        # add logic for chunking pdfs etc
        # this should be broken out to a method
        # modify in helpersfor other file types
        # this can be database vector or sql also then that would populate data
        """
        try:
            if self.source_type == SourceType.FILE:
                fileName = download_from_supa_base(self.source_name, "scraped_data")
                self.data = load_file(fileName)
                self.estimated_tokens = len(self.data)

            return self.data
        except Exception as e:
            print(f"Error getting context data: {e}")
            raise
