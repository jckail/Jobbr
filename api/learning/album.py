import fastapi
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_session
from models import AlbumBase, Album, Band
from pydantic import UUID4
from typing import List

tags_metadata = ["albums"]
router = fastapi.APIRouter(tags=tags_metadata)


@router.get("/api/album/")
async def get_album(
    album_id: UUID4 = None,
    album_name: str = None,
    session: Session = Depends(dependency=get_session),
) -> Album:
    """
    Get an album by ID or name.

    Args:
        album_id (UUID4, optional): The ID of the album.
        album_name (str, optional): The name of the album.
        session (Session, optional): The database session. Defaults to Depends(dependency=get_session).

    Returns:
        Album: The album.

    Raises:
        HTTPException: If the album is not found.

    """
    if album_id is not None:
        album = session.query(Album).get(album_id)
    elif album_name is not None:
        album = session.query(Album).filter(Album.title == album_name).first()
    else:
        raise HTTPException(
            status_code=400, detail="Please provide either album ID or album name"
        )

    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    return album


@router.post("/api/album/createAlbum")
async def create_album(
    album: AlbumBase, session: Session = Depends(dependency=get_session)
) -> Album:
    from .band import get_band

    """
    Create a new album.

    Args:
        album (AlbumBase): The album data.
        session (Session, optional): The database session. Defaults to Depends(dependency=get_session).

    Returns:
        Album: The created album.

    """
    try:
        new_album = Album(**album.dict())
        if new_album.band_id is not None:
            band = session.query(Band).filter(Band.id == new_album.band_id).first()
        if band is None:
            raise fastapi.HTTPException(status_code=404, detail="band_id not found")

        session.add(new_album)
        session.commit()
        session.refresh(new_album)
        return new_album
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/album/{album_id}")
async def delete_album(
    album_id: UUID4, session: Session = Depends(dependency=get_session)
) -> None:
    """
    Delete an album.

    Args:
        album_id (UUID4): The ID of the album to delete.
        session (Session, optional): The database session. Defaults to Depends(dependency=get_session).

    Raises:
        HTTPException: If the album is not found.

    """
    album = session.query(Album).get(album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    session.delete(album)
    session.commit()


@router.put("/api/album/{album_id}")
async def update_album(
    album_id: UUID4,
    album: AlbumBase,
    session: Session = Depends(dependency=get_session),
) -> Album:
    """
    Update an album.

    Args:
        album_id (UUID4): The ID of the album to update.
        album (AlbumBase): The updated album data.
        session (Session, optional): The database session. Defaults to Depends(dependency=get_session).

    Returns:
        Album: The updated album.

    Raises:
        HTTPException: If the album is not found.

    """
    existing_album = session.query(Album).get(album_id)
    if not existing_album:
        raise HTTPException(status_code=404, detail="Album not found")

    for field, value in album.dict().items():
        setattr(existing_album, field, value)

    session.commit()
    session.refresh(existing_album)
    return existing_album


@router.get("/api/album/band/{band_id}")
async def get_albums_by_band(
    band_id: UUID4,
    session: Session = Depends(dependency=get_session),
) -> List[Album]:
    """
    Get all albums by band ID.

    Args:
        band_id (UUID4): The ID of the band.
        session (Session, optional): The database session. Defaults to Depends(dependency=get_session).

    Returns:
        List[Album]: The list of albums.

    """
    albums = session.query(Album).filter(Album.band_id == band_id).all()
    return albums
