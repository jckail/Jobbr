from sqlmodel import create_engine, SQLModel, Session


DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/exampledb"

engine = create_engine(DATABASE_URL)  # , echo=True big saftey hazard


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
