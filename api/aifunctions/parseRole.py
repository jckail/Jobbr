import fastapi

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_session
from models import URL, LLM, Stg_Role, Stg_RoleBase, AIEvent, URLBase
from sqlalchemy import desc

from .app_ai import JobbrAI

from .modelHelpers import modelDecider, findOrAddURL, fileToModelLoader

tags_metadata = ["parse"]
router = fastapi.APIRouter(tags=tags_metadata)

FILE_LOCATION = "scraped_data"


@router.post("/api/parse/stg_role", response_model=Stg_Role)
async def parse_roleFile(input_url: str, session: Session = Depends(get_session)):
    """
    Create a new URL entry as a role type.

    Args:
        request (CreateURLRequest): The request body containing the URL data.
        session (Session, optional): The database session. Defaults to Depends(get_session).

    Returns:
        URL: The created URL object.
    """
    url = findOrAddURL(input_url, session)
    try:
        max_tries = 3
        tries = 0

        while tries < max_tries:

            tries += 1
            model, file = modelDecider(url, tries)

            print(f"\n---\n{model} {file}\n---\n")
            try:

                stg_rolebase, ai_info = fileToModelLoader(
                    model, file, Stg_RoleBase, AIEvent.PARSE_ROLE_HTML
                )

                break

            except Exception as e:
                print(f"Failed to parse role HTML: {str(e)} try {str(tries)}")
        sr = Stg_Role(
            **stg_rolebase.model_dump(),
            **ai_info,
            url_id=url.id,
            url=url.url,
        )
        sr.saveModel()
        return sr

    except Exception as e:
        session.rollback()  # Rollback in case of failure
        raise HTTPException(status_code=400, detail=str(e))
