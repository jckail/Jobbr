import fastapi

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_session
from models import URL, LLM, Stg_Role, Stg_RoleBase, AIEvent, URLBase
from sqlalchemy import desc

from .app_ai import JobbrAI
from api.scraper.helpers import createURL

tags_metadata = ["parse"]
router = fastapi.APIRouter(tags=tags_metadata)

FILE_LOCATION = "scraped_data"


def modelDecider(url, tries):
    try:

        if url.html_len < 15500 and tries == 1:
            return LLM.GPT3, url.htmlPath
        if url.parseText_len < 15500 and tries == 1:
            return LLM.GPT3, url.parseTextPath
        if url.parseVisible_len < 15500 and tries == 1:
            return LLM.GPT3, url.parseVisibleTextPath

        if url.html_len < 30000 and tries < 3:
            return LLM.GPT4, url.htmlPath
        if url.parseText_len < 30000 and tries < 3:
            return LLM.GPT4, url.parseTextPath
        if url.parseVisible_len < 30000 and tries < 3:
            return LLM.GPT4, url.parseVisibleTextPath

        if url.html_len < 60000 and tries < 3:
            return LLM.GPT4, url.htmlPath
        if url.parseText_len < 60000 and tries < 3:
            return LLM.GPT4, url.parseTextPath
        if url.parseVisible_len < 60000 and tries < 3:
            return LLM.GPT4, url.parseVisibleTextPath

        if url.html_len < 90000 and tries < 3:
            return LLM.GPT4, url.htmlPath
        if url.parseText_len < 90000 and tries < 3:
            return LLM.GPT4, url.parseTextPath
        if url.parseVisible_len < 90000 and tries < 3:
            return LLM.GPT4, url.parseVisibleTextPath

        if tries == 3:
            return LLM.CLAUD3_OPUS, url.parseTextPath

        return None, None

    except Exception as e:
        print(f"A modelDecider error occurred: {e}")
        return None, None


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
    try:
        url = (
            session.query(URL)
            .filter(URL.url == input_url)
            .order_by(desc(URL.created_at))
            .first()
        )
        if not url:
            try:
                ub = URLBase(url=input_url)
                url = createURL(ub)
                session.add(url)
                session.commit()
                session.refresh(url)

            except Exception as e:
                session.rollback()  # Rollback in case of failure
                raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"URL not found {e}")

    try:
        max_tries = 3
        tries = 0

        while tries < max_tries:

            tries += 1
            model, file = modelDecider(url, tries)

            try:

                ai = JobbrAI(model)
                f = Stg_RoleBase.__doc__

                userMessage = f" Convert the following job posting text to exactly the desired json format {f}. Do not add in any new field names use only the ones I have previously provided. If there are any values that cannot be calculated return those as None. If there is a mention of 'not found' assume the role has been filled and the status is closed. Here is the job posting"

                ci = ai.loadContextFile(file)
                ai.context.specified_context_ids = [ci.id]

                stg_rolebase, ai_info = ai.parseToDataModel(
                    Stg_RoleBase,
                    AIEvent.PARSE_ROLE_HTML,
                    userMessage,
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
