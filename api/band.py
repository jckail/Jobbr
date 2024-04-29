import fastapi
from fastapi import Depends
from sqlalchemy.orm import Session
from db import get_session
from models import Album, Band, BandCreate
from typing import Optional
from pydantic import UUID4
from typing import List


tags_metadata = ["band"]
router = fastapi.APIRouter(tags=tags_metadata)


@router.get("/api/band/", response_model=Band)
async def get_band(
    band_id: Optional[UUID4] = None,
    name: Optional[str] = None,
    session: Session = Depends(get_session),
) -> Band:
    """
    Get a band by its ID or name.

    Args:
        band_id (UUID4, optional): The ID of the band. Defaults to None.
        name (str, optional): The name of the band. Defaults to None.
        session (Session, optional): The database session. Defaults to Depends(get_session).

    Returns:
        Band: The band object.

    Raises:
        HTTPException: If the band is not found or the ID and name parameters are missing.
    """
    if band_id is not None:
        band = session.query(Band).filter(Band.id == band_id).first()
        if band is None:
            raise fastapi.HTTPException(status_code=404, detail="Band not found")
        return band
    elif name is not None:
        band = session.query(Band).filter(Band.name == name).first()
        if band is None:
            raise fastapi.HTTPException(status_code=404, detail="Band not found")
        return band
    else:
        raise fastapi.HTTPException(
            status_code=400, detail="ID or name parameter is required"
        )


@router.post("/api/band/create", response_model=BandCreate)
async def create_band(
    band_data: BandCreate, session: Session = Depends(get_session)
) -> Band:
    """
    Create a new band.

    Args:
        band_data (BandCreate): The data for creating the band.
        session (Session, optional): The database session. Defaults to Depends(get_session).

    Returns:
        Band: The created band object.

    Raises:
        HTTPException: If the band name already exists.
    """
    existing_band = session.query(Band).filter(Band.name == band_data.name).first()
    if existing_band:
        raise fastapi.HTTPException(status_code=400, detail="Band name already exists")

    band = Band(
        name=band_data.name, genre=band_data.genre, date_formed=band_data.date_formed
    )
    session.add(band)
    session.commit()  # Commit the session after adding the band

    if band_data.album:
        for album in band_data.album:
            album_obj = Album(
                title=album.title,
                release_date=Album.validate_release_date(album.release_date),
                band=band,
            )
            session.add(album_obj)

    session.commit()
    session.refresh(band)

    return band


@router.put("/api/band/{band_id}", response_model=Band)
async def update_band(
    band_id: UUID4,
    band_data: Optional[BandCreate] = None,
    session: Session = Depends(get_session),
) -> Band:
    """
    Update an existing band.

    Args:
        band_id (UUID4): The ID of the band to update.
        band_data (Optional[BandCreate], optional): The updated data for the band. Defaults to None.
        session (Session, optional): The database session. Defaults to Depends(get_session).

    Returns:
        Band: The updated band object.

    Raises:
        HTTPException: If the band is not found.
    """
    band = session.query(Band).filter(Band.id == band_id).first()
    if band is None:
        raise fastapi.HTTPException(status_code=404, detail="Band not found")

    if band_data:
        band.name = band_data.name
        band.genre = band_data.genre
        band.date_formed = band_data.date_formed

    session.commit()
    session.refresh(band)
    return band


@router.delete("/api/band/{band_id}")
async def delete_band(band_id: UUID4, session: Session = Depends(get_session)):
    """
    Delete a band by its ID.

    Args:
        band_id (UUID4): The ID of the band to delete.
        session (Session, optional): The database session. Defaults to Depends(get_session).

    Raises:
        HTTPException: If the band is not found.
    """
    band = session.query(Band).filter(Band.id == band_id).first()
    if band is None:
        raise fastapi.HTTPException(status_code=404, detail="Band not found")

    session.delete(band)
    session.commit()


@router.get("/api/bands/", response_model=List[Band])
async def get_bands(session: Session = Depends(get_session)) -> List[Band]:
    """
    Get a list of all bands.

    Args:
        session (Session, optional): The database session. Defaults to Depends(get_session).

    Returns:
        List[Band]: The list of all bands.
    """
    bands = session.query(Band).all()
    return bands
