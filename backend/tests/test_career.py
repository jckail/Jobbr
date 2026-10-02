"""No paid calls: fake the Runner at the SDK boundary."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from jobbr import career, extract
from jobbr.config import Settings
from jobbr.models import ExtractMethod, Job, Profile
from jobbr.schemas import JobExtraction
from tests.conftest import ARTICLE


@pytest.fixture
def configured(monkeypatch):
    settings = Settings(openai_api_key="test-key", ai_timeout_s=0.1, _env_file=None)
    monkeypatch.setattr(career, "get_settings", lambda: settings)
    monkeypatch.setattr(extract, "get_settings", lambda: settings)
    return settings


def facts():
    return (
        Job(company_id=1, title="Data Engineer", skills=["python", "sql"]),
        Profile(name="Ada", resume_text="Built Python pipelines.", skills=["python"]),
    )


def draft(kind="cover_letter", quote="Built Python pipelines."):
    return career.CareerDraft(
        cover_letter="Dear hiring team, I built Python pipelines."
        if kind == "cover_letter"
        else None,
        interview_questions=[]
        if kind == "cover_letter"
        else [
            career.InterviewQuestion(
                question=f"How would you approach pipeline challenge {number}?",
                answer_outline=["Discuss Built Python pipelines.; supply a real SQL example."],
                evidence_quotes=[quote],
            )
            for number in range(5)
        ],
        strengths=["Python"],
        gaps=["SQL experience needs confirmation"],
        questions_to_ask=["What are the team's data reliability goals?"],
        evidence_quotes=[quote],
        review_notes=["Verify claims before use."],
    )


def fake_result(output):
    return SimpleNamespace(
        final_output=output,
        context_wrapper=SimpleNamespace(usage=SimpleNamespace(input_tokens=123, output_tokens=45)),
    )


def test_no_key_never_calls_runner(monkeypatch):
    settings = Settings(openai_api_key=None, _env_file=None)
    monkeypatch.setattr(career, "get_settings", lambda: settings)

    async def fail(*args, **kwargs):
        pytest.fail("No-key workflow must not invoke SDK")

    monkeypatch.setattr(career.Runner, "run", fail)
    job, profile = facts()
    with pytest.raises(career.AIUnavailable):
        asyncio.run(career.generate_career(job, "Acme", profile, "cover_letter"))


@pytest.mark.parametrize("kind", ["cover_letter", "interview_prep"])
def test_structured_generation_and_privacy(configured, monkeypatch, kind):
    async def run(agent, content, **kwargs):
        source = json.loads(content)
        assert source["job"]["company"] == "Acme"
        assert source["profile"]["resume_text"] == "Built Python pipelines."
        assert agent.output_type is career.CareerDraft
        assert agent.tools == []
        assert agent.model_settings.store is False
        assert kwargs["max_turns"] == 2
        assert kwargs["run_config"].tracing_disabled is True
        assert kwargs["run_config"].trace_include_sensitive_data is False
        return fake_result(draft(kind))

    monkeypatch.setattr(career.Runner, "run", run)
    job, profile = facts()
    result = asyncio.run(career.generate_career(job, "Acme", profile, kind))
    assert result.kind == kind
    assert result.input_tokens == 123
    assert result.requires_review


def test_rejects_invented_evidence(configured, monkeypatch):
    async def run(*args, **kwargs):
        return fake_result(draft(quote="Led 100 engineers at Imaginary Corp."))

    monkeypatch.setattr(career.Runner, "run", run)
    job, profile = facts()
    with pytest.raises(career.CareerGenerationError, match="evidence"):
        asyncio.run(career.generate_career(job, "Acme", profile, "cover_letter"))


@pytest.mark.parametrize("failure", ["provider", "timeout", "invalid"])
def test_failure_has_no_fake_draft(configured, monkeypatch, failure):
    async def run(*args, **kwargs):
        if failure == "timeout":
            await asyncio.sleep(1)
        if failure == "invalid":
            return fake_result({"cover_letter": "not a complete structured output"})
        raise RuntimeError("sensitive provider message")

    monkeypatch.setattr(career.Runner, "run", run)
    job, profile = facts()
    with pytest.raises(career.CareerGenerationError) as caught:
        asyncio.run(career.generate_career(job, "Acme", profile, "cover_letter"))
    assert "sensitive" not in str(caught.value)
    assert ("timed out" in str(caught.value)) == (failure == "timeout")


def test_empty_profile_rejected(configured):
    job, _ = facts()
    with pytest.raises(career.CareerInputError):
        asyncio.run(career.generate_career(job, "Acme", Profile(), "cover_letter"))


def test_jsonld_precedes_paid_extraction(configured, monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("Structured page must not invoke paid extraction")

    monkeypatch.setattr(extract, "llm_extract", fail)
    result = extract.extract("Posting text", html=ARTICLE)
    assert result.method is ExtractMethod.jsonld
    assert result.model is None


def test_ai_extraction_uses_sdk(configured, monkeypatch):
    async def run(agent, content, **kwargs):
        assert agent.output_type is JobExtraction
        assert "Python" in json.loads(content)["posting"]
        return fake_result(JobExtraction(company="Acme", title="Engineer", skills=["Python"]))

    monkeypatch.setattr(career.Runner, "run", run)
    result = extract.extract("Python engineering role")
    assert result.method is ExtractMethod.llm
    assert result.data.skills == ["python"]
    assert result.input_tokens == 123


def test_extraction_failure_records_fallback(configured, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("private provider details")

    monkeypatch.setattr(extract, "llm_extract", fail)
    result = extract.extract("Engineer\nPython role")
    assert result.method is ExtractMethod.heuristic
    assert result.error
    assert "offline heuristics" in result.error
    assert "private provider details" not in result.error
