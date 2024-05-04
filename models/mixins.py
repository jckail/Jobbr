import time
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_mixin
from sqlalchemy.dialects.postgresql import JSONB, ARRAY


@declarative_mixin
class BaseMixin:
    # Primary key with UUID
    # id = Column(UUID, default=uuid.uuid4, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow
    )
    created_at_utc = Column(Integer, default=int(time.time()), nullable=False)
    updated_at_utc = Column(
        Integer, default=int(time.time()), nullable=False, onupdate=int(time.time())
    )


@declarative_mixin
class AIBaseMixin:
    # Primary key with UUID
    # id = Column(String, default=lambda: str(uuid.uuid4()), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow
    )
    created_at_utc = Column(Integer, default=lambda: int(time.time()), nullable=False)
    updated_at_utc = Column(
        Integer,
        default=lambda: int(time.time()),
        nullable=False,
        onupdate=lambda: int(time.time()),
    )
    ai_app_event_id = Column(String, nullable=True)
    specified_context_ids = Column(ARRAY(String), default=None)
    context_id = Column(String, nullable=True)  # Assuming UUIDs are stored as strings
    extra_data = Column(JSONB, default=None)
