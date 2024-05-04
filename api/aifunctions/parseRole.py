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

claude_sample = """{
  "company_name": "Red Lobster",
  "title": "Server",
  "job_category": "Restaurant",
  "posting_date": "2024-04-27",
  "employment_type": "Full-time, Part-time",
  "employment_term_days": null,
  "description": "As a Server at Red Lobster, you will enhance guest experiences by offering personalized service, suggestions and pairings.",
  "team": null,
  "team_description": null,
  "expectations": "Daily tasks will include taking orders accurately, delivering hot food promptly, clearing tables, and managing transactions!",
  "location": ["Aurora, Colorado"],
  "remote": "No",
  "in_person": "Yes",
  "travel": null,
  "responsibilities": ["taking orders accurately", "delivering hot food promptly", "clearing tables", "managing transactions"],
  "qualifications": ["Must be of legal age to serve alcohol based on state requirements"],
  "soft_skills": ["Multi-tasking", "listening", "communication skills"],
  "tool_experience": ["Point of Sale systems"], // This is an inferred field since servers generally use this, not explicitly mentioned.
  "programming_languages": null,
  "technical_skills": null,
  "certifications": null,
  "years_of_experience": null,
  "prior_experience_description": null,
  "individual_contributor": true,
  "people_manager": false,
  "estimated_career_level": "Entry",
  "education_requirement": null,
  "compensation_type": "Hourly",
  "estimated_min_compensation": 11,
  "estimated_max_compensation": 25,
  "compensation_description": "$11.40 - $25.00 per hour",
  "unlimited_pto": null,
  "pto_and_benefits": null,
  "role_quirks": null,
  "ai_analysis": null,
  "estimated_status": "Active",
  "external_links": [],
  "industry": "Restaurant",
  "job_id": "532620979",
  "offers_401k": null
}"""


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
            model = LLM.CLAUD3_OPUS
            print(f"\n---\n{model} {file}\n---\n")
            try:

                ai = JobbrAI(model)
                f = Stg_RoleBase.__doc__

                userMessage = f" Convert the following job posting text to exactly the desired json format {f}. Do not add in any new field names use only the ones I have previously provided. If there are any values that cannot be calculated return those as None. If there is a mention of 'not found' assume the role has been filled and the status is closed. Here is the job posting"

                if model == LLM.CLAUD3_OPUS:
                    userMessage = "Parse the following context into into JSON format"

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
