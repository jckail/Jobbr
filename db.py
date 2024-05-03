from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy.exc import SQLAlchemyError


# DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/exampledb"
DATABASE_URL = "postgresql+psycopg2://postgres:your-super-secret-and-long-postgres-password@localhost:5432/postgres"

engine = create_engine(DATABASE_URL)  # , echo=True big saftey hazard


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


def saveDataModel(data_model, session=None, engine=None):
    try:
        if not engine:
            engine = create_engine(DATABASE_URL)

        if not session:
            with Session(engine) as session:
                session.add(data_model)
                session.commit()
                session.refresh(data_model)
                return data_model, session, engine

        session.add(data_model)
        session.commit()
        session.refresh(data_model)

        return data_model, session, engine
    except SQLAlchemyError as e:
        print(f"An error occurred with the database operation: saveDataModel - {e}")
        # Optionally, re-raise the exception if you want it to propagate
        raise
    except Exception as e:
        print(f"An unexpected error occurred: saveDataModel - {e}")
        # Optionally, re-raise the exception if you want it to propagate
        raise
