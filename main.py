from fastapi import FastAPI
from api import band, album, user, special


# TODO: probably want to have a user for "alembic" in the database
# Removing this so alembic manages the database vs fastApi
# alembic revision --autogenerate -m "initial migration"
# alembic upgrade head
# from db import init_db, get_session
# from contextlib import asynccontextmanager
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     init_db()
#     yield
# app = FastAPI(lifespan=lifespan)


app = FastAPI(
    title="Hello World",
    description="Learning to code",
    version="0.0.1",
    contact={"name": "Jordan", "email": "jckail13@gmail.com"},
    license_info={"name": "MIT"},
)


app.include_router(band.router)
app.include_router(album.router)
app.include_router(user.router)
app.include_router(special.router)
