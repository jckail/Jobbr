from fastapi import HTTPException
from sqlalchemy.orm import Session
from db import get_session
from models import URL, LLM, Stg_Role, Stg_RoleBase, AIEvent, URLBase
from sqlalchemy import desc

from .app_ai import JobbrAI
from api.scraper.helpers import createURL
from pydantic import BaseModel


def tryModelRun(
    model,
    file,
    modelDecider,
    baseModel: BaseModel,
    aiEvent: AIEvent,
    max_tries=3,
):
    try:
        tries = 0
        while tries < max_tries:

            tries += 1
            model, file = modelDecider

            print(f"\n---\n{model} {file}\n---\n")
            try:

                return fileToModelLoader(model, file, baseModel, aiEvent)

            except Exception as e:
                print(f"Failed to parse role HTML: {str(e)} try {str(tries)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def fileToModelLoader(model, file, baseModel: BaseModel, aiEvent: AIEvent):
    ai = JobbrAI(model)
    ai.context.specified_context_ids = [ai.loadContextFile(file).id]
    return ai.parseToDataModel(
        baseModel,
        aiEvent,
        " ",
    )


def findOrAddURL(input_url: str, session: Session):
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
    return url


def estimate_cost(num_tokens, rate_per_million=10.0):
    print((num_tokens / 1_000_000) * rate_per_million)
    return float(round(float((float(num_tokens) / 1_000_000) * rate_per_million), 5))


def modelDecider(url, tries):
    """
    TODO: add in to ai run config to indicate why a model was chosen and by what logic
    input should be just path, tries

    thoughts
    not passing multiple fields of the url
    outside the function it should be intelligent to try first with HTMLS
    inside the function it should

    """
    try:

        if url.html_len < 8500 and tries == 1:
            print(f"\n -- \n Estimated Cost: {str(estimate_cost(url.html_len))}")
            return LLM.GPT4, url.htmlPath
        if url.parseText_len < 8500 and tries == 1:
            print(f"\n -- \n Estimated Cost: {str(estimate_cost(url.parseText_len))}")
            return LLM.GPT4, url.parseTextPath
        if url.parseVisible_len < 8500 and tries == 1:
            print(
                f"\n -- \n Estimated Cost: {str(estimate_cost(url.parseVisible_len))}"
            )
            return LLM.GPT4, url.parseVisibleTextPath

        if url.html_len < 15500 and tries == 1:
            print(f"\n -- \n Estimated Cost: {str(estimate_cost(url.html_len,.5))}")
            return LLM.GPT3, url.htmlPath
        if url.parseText_len < 15500 and tries == 1:
            print(
                f"\n -- \n Estimated Cost: {str(estimate_cost(url.parseText_len,.5))}"
            )
            return LLM.GPT3, url.parseTextPath
        if url.parseVisible_len < 15500 and tries == 1:
            print(
                f"\n -- \n Estimated Cost: {str(estimate_cost(url.parseVisible_len,.5))}"
            )
            return LLM.GPT3, url.parseVisibleTextPath

        if url.html_len < 30000 and tries < 3:
            print(f"\n -- \n Estimated Cost: {str(estimate_cost(url.html_len))}")
            return LLM.GPT4, url.htmlPath
        if url.parseText_len < 30000 and tries < 3:
            print(f"\n -- \n Estimated Cost: {str(estimate_cost(url.parseText_len))}")
            return LLM.GPT4, url.parseTextPath
        if url.parseVisible_len < 30000 and tries < 3:
            print(
                f"\n -- \n Estimated Cost: {str(estimate_cost(url.parseVisible_len))}"
            )
            return LLM.GPT4, url.parseVisibleTextPath

        if url.html_len < 60000 and tries < 3:
            print(f"\n -- \n Estimated Cost: {str(estimate_cost(url.html_len))}")
            return LLM.GPT4, url.htmlPath
        if url.parseText_len < 60000 and tries < 3:
            print(f"\n -- \n Estimated Cost: {str(estimate_cost(url.parseText_len))}")
            return LLM.GPT4, url.parseTextPath
        if url.parseVisible_len < 60000 and tries < 3:
            print(
                f"\n -- \n Estimated Cost: {str(estimate_cost(url.parseVisible_len))}"
            )
            return LLM.GPT4, url.parseVisibleTextPath

        if url.html_len < 90000 and tries < 3:
            print(f"\n -- \n Estimated Cost: {str(estimate_cost(url.html_len))}")
            return LLM.GPT4, url.htmlPath
        if url.parseText_len < 90000 and tries < 3:
            print(f"\n -- \n Estimated Cost: {str(estimate_cost(url.parseText_len))}")
            return LLM.GPT4, url.parseTextPath
        if url.parseVisible_len < 90000 and tries < 3:
            print(
                f"\n -- \n Estimated Cost: {str(estimate_cost(url.parseVisible_len))}"
            )
            return LLM.GPT4, url.parseVisibleTextPath

        if tries == 3:
            return LLM.CLAUD3_OPUS, url.parseTextPath

        return None, None

    except Exception as e:
        print(f"A modelDecider error occurred: {e}")
        return None, None
