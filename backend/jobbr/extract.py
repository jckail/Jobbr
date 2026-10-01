"""Extraction pipeline: schema.org JSON-LD (free), Claude structured output, heuristic fallback."""

import time
from dataclasses import dataclass

import anthropic

from .config import get_settings
from .models import ExtractMethod
from .parsing import heuristic_job, jsonld_job
from .schemas import JobExtraction
from .skills import find_skills, normalize_skills

# USD per million tokens (input, output)
PRICES = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-4-5": (3.0, 15.0),
}

SYSTEM = (
    "You extract structured data from job postings. Be faithful to the text; use null/empty when "
    "something is not stated. Normalise skills to short lowercase canonical names "
    "(e.g. 'postgres', 'kubernetes'). Convert pay to ANNUAL whole-number figures. "
    "Keep bullets short. "
    "ai_take is one candid sentence on who would thrive and any red flags."
)


@dataclass
class Result:
    data: JobExtraction
    method: ExtractMethod
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: str | None = None  # non-fatal: why we fell back


def llm_extract(text: str, hint: str | None = None) -> tuple[JobExtraction, int, int]:
    s = get_settings()
    client = anthropic.Anthropic(api_key=s.anthropic_api_key, max_retries=2, timeout=60)
    content = (
        (f"Hint: {hint}\n\n" if hint else "")
        + "<posting>\n"
        + text[: s.max_input_chars]
        + "\n</posting>"
    )
    resp = client.messages.create(
        model=s.model,
        max_tokens=2000,
        system=SYSTEM,
        tools=[
            {
                "name": "record_job",
                "description": "Record the structured job posting.",
                "input_schema": JobExtraction.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "record_job"},
        messages=[{"role": "user", "content": content}],
    )
    block = next(b for b in resp.content if b.type == "tool_use")
    data = JobExtraction.model_validate(block.input)
    return data, resp.usage.input_tokens, resp.usage.output_tokens


def extract(
    text: str, html: str | None = None, title: str | None = None, company: str | None = None
) -> Result:
    s = get_settings()
    t0 = time.monotonic()
    error = None

    if s.llm_enabled:
        try:
            data, i, o = llm_extract(
                text, hint=" / ".join(x for x in (company, title) if x) or None
            )
            pin, pout = PRICES.get(s.model, (3.0, 15.0))
            return Result(
                data,
                ExtractMethod.llm,
                s.model,
                i,
                o,
                round(i * pin / 1e6 + o * pout / 1e6, 5),
                int((time.monotonic() - t0) * 1000),
            )
        except Exception as e:
            error = f"LLM extraction failed ({type(e).__name__}); used fallback."

    ld = jsonld_job(html) if html else None
    if ld:
        method, data = ExtractMethod.jsonld, ld
    else:
        method, data = ExtractMethod.heuristic, heuristic_job(text, title, company)
    if company:
        data.company = company
    if title:
        data.title = title
    data.skills = normalize_skills(data.skills) or find_skills(text)
    return Result(data, method, None, 0, 0, 0.0, int((time.monotonic() - t0) * 1000), error)
