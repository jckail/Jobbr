from sqlmodel import Field, AutoString
from .urlBase import URLBase
import uuid
from ..enums import URLType
from pydantic import DirectoryPath, FilePath


class URL(URLBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    type: URLType
    directory: DirectoryPath | None = Field(sa_type=AutoString)
    snapshotPath: FilePath | None = Field(sa_type=AutoString)
    snapshot_len: int | None
    htmlPath: FilePath | None = Field(sa_type=AutoString)
    html_len: int | None
    parseTextPath: FilePath | None = Field(sa_type=AutoString)
    parseText_len: int | None
    parseVisibleTextPath: FilePath | None = Field(sa_type=AutoString)
    parseVisible_len: int | None


# if __name__ == "__main__":
#     from sqlalchemy.orm import Session
#     from db import get_session

#     session = get_session()

#     # Example function to insert a URL
#     def insert_url(session: Session, url: str):
#         new_url = URL(url=url)
#         session.add(new_url)
#         session.commit()

#     # Example usage
#     engine = create_engine("postgresql://user:password@localhost/dbname")
#     with Session(engine) as session:
#         insert_url(session, "https://example.com")
