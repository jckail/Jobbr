from datetime import datetime


from sqlalchemy import Column, DateTime
from sqlalchemy.orm import declarative_mixin

# TODO: Add in mixin for UUID so that every record generated has unique identifier
# TODO: Add in mixin for "user_id_data" so that we tag every record of the database associated with a users session
# TODO: Add in session_id so that for every login or signin a session is generated or something there of to track user behavior


@declarative_mixin
class Timestamp:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
