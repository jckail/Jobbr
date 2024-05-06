import fastapi

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_session
from models import URL, URLBase

from api.scraper.helpers import createURL
from typing import List


tags_metadata = ["url"]
router = fastapi.APIRouter(tags=tags_metadata)

FILE_LOCATION = "scraped_data"


@router.post("/api/role_url", response_model=URL)
async def add_role_url(url: URLBase, session: Session = Depends(get_session)) -> URL:
    """
    Create a new URL entry as a role type.

    Args:
        request (CreateURLRequest): The request body containing the URL data.
        session (Session, optional): The database session. Defaults to Depends(get_session).

    Returns:
        URL: The created URL object.
    """
    try:

        new_url = createURL(url)

        session.add(new_url)
        session.commit()
        session.refresh(new_url)
        return new_url
    except Exception as e:
        session.rollback()  # Rollback in case of failure
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/role_urls", response_model=List[URL])
async def add_role_urls(
    urls: List[URLBase], session: Session = Depends(get_session)
) -> List[URL]:
    """
    Create new URL entries as role types.

    Args:
        urls (List[URLBase]): The list of URL data objects.
        session (Session, optional): The database session. Defaults to Depends(get_session).

    Returns:
        List[URL]: The list of created URL objects.
    """
    created_urls = []
    try:
        for url_data in urls:
            new_url = createURL(url_data, "role_url")
            session.add(new_url)
            session.commit()
            session.refresh(new_url)
            created_urls.append(new_url)
        return created_urls
    except Exception as e:
        session.rollback()  # Rollback in case of failure
        raise HTTPException(status_code=400, detail=str(e))
