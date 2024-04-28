from fastapi import FastAPI, Depends, HTTPException


from db import init_db, get_session
from models import BandCreate, Band, Album, AlbumBase
from sqlmodel import Session


BANDS = [
    {
        "ID": 1,
        "name": "The Kinks",
        "genre": "rock",
        "albums": [{"title": "Master of Reality", "releaste_date": "1971-07-21"}],
    }
]

# TODO: probably want to have a user for "alembic" in the database
# Removing this so alembic manages the database vs fastApi
# alembic revision --autogenerate -m "initial migration"
# alembic upgrade head
# from contextlib import asynccontextmanager
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     init_db()
#     yield
# app = FastAPI(lifespan=lifespan)

app = FastAPI()


@app.post("/bands", response_model=BandCreate)
async def create_band(
    band_data: BandCreate, session: Session = Depends(get_session)
) -> Band:

    band = Band(
        name=band_data.name, genre=band_data.genre, date_formed=band_data.date_formed
    )
    session.add(band)
    session.commit()  # Commit the session after adding the band

    if band_data.albums:
        for album in band_data.albums:

            album_obj = Album(
                title=album.title,
                release_date=Album.validate_release_date(album.release_date),
                band=band,
            )
            session.add(album_obj)

    session.commit()
    session.refresh(band)

    return band


@app.post("/albums")
async def create_album(
    album_data: AlbumBase, session: Session = Depends(dependency=get_session)
) -> Album:
    band = session.query(Band).get(album_data.band_id)
    if not band:
        raise HTTPException(status_code=404, detail="Band not found")

    album = Album(
        title=album_data.title, release_date=album_data.release_date, band=band
    )
    session.add(album)
    session.commit()
    session.refresh(album)
    return album
