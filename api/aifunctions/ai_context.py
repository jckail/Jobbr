from uuid import UUID, uuid4

from models import (
    SourceType,
    AI_Context,
)


from typing import Optional, List, Any
from .ai_context_item import AI_CONTEXT_ITEM

## will create a context ownership model


### AI contains context items context items are not bound to a particualr ai
class AI_CONTEXT:
    def __init__(
        self,
        app_ai_id: UUID,
        specified_context_ids: Optional[List[UUID]] = None,
        context_items: Optional[List[AI_CONTEXT_ITEM]] = None,
        extra_data: Optional[dict] = None,
    ):
        try:
            if not isinstance(app_ai_id, UUID):
                raise ValueError("app_ai_id must be a valid UUID instance.")

            self.app_ai_id = app_ai_id
            self.id = uuid4()

            if specified_context_ids is None:
                specified_context_ids = []
            else:
                if not all(isinstance(cid, UUID) for cid in specified_context_ids):
                    raise ValueError(
                        "All specified_context_ids must be valid UUID instances."
                    )
            self.specified_context_ids = specified_context_ids

            self.context_items = {}
            if context_items:
                if not all(isinstance(item, AI_CONTEXT_ITEM) for item in context_items):
                    raise TypeError(
                        "All context_items must be instances of AI_CONTEXT_ITEM."
                    )
                for ci in context_items:
                    self.context_items[ci.id] = ci

            self.extra_data = extra_data if extra_data is not None else {}

            self.save()
        except ValueError as e:
            print(f"Error initializing AI_CONTEXT: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            raise

    def save(self):
        AI_Context(
            id=self.id,
            app_ai_id=self.app_ai_id,
            specified_context_ids=self.specified_context_ids,
            context_items=self.context_items.keys(),
            extra_data=self.extra_data,
        ).saveModel()

    def add_existing_ai_context_item(self, ci: AI_CONTEXT_ITEM):
        self.context_items[ci.id] = ci

    def add_ai_context_item(
        self,
        source_name: str,
        source_type: SourceType,
        source_id: Optional[UUID] = None,
        description: str = None,
        alias: str = None,
        data: Any = None,
        estimated_tokens: int = None,
        authorized_users: List[
            str  # eventually when context is added this will be
        ] = None,  # a list of users allowed to access the context
        extra_data: Optional[dict] = None,
    ):

        ci = AI_CONTEXT_ITEM(
            context_owner_id=self.id,
            source_name=source_name,
            source_type=source_type,
            source_id=source_id,
            description=description,
            alias=alias,
            data=data,
            estimated_tokens=estimated_tokens,
            authorized_users=authorized_users,
            extra_data=extra_data,
        )
        self.context_items[ci.id] = ci

        return ci
