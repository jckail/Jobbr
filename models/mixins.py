import time
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, UUID, Integer
from sqlalchemy.orm import declarative_mixin


@declarative_mixin
class BaseMixin:
    # Primary key with UUID

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow
    )
    created_at_utc = Column(Integer, default=int(time.time()), nullable=False)
    updated_at_utc = Column(
        Integer, default=int(time.time()), nullable=False, onupdate=int(time.time())
    )

    # # Example columns for user/session data
    # user_id = Column(
    #     String(36)
    # )  # Assuming user IDs are also UUIDs, adjust the type as needed
    # session_id = Column(String(36))  # Assuming session IDs are UUIDs

    ## UUID location type array[assoc UUIDs] self etc #
    ## Back updates to UUID
    ## UUID string # can be an action, entity, anything
    ## Location is where the UUID lives
    ## type is a UUID Enum
    ## UUID Enums will have descriptions eventually


## APIUSERID UUTYPE UUID LOCATION
