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
    settings = Settings(
        ai_provider="openai", openai_api_key="test-key", ai_timeout_s=0.1, _env_file=None
    )
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
    settings = Settings(ai_provider="openai", openai_api_key=None, _env_file=None)
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


@pytest.mark.parametrize("kind", ["cover_letter", "interview_prep"])
def test_claude_generation_reuses_evidence_validation_without_openai(monkeypatch, kind):
    import httpx  # noqa: PLC0415

    from jobbr import anthropic_provider  # noqa: PLC0415

    settings = Settings(
        ai_provider="anthropic",
        anthropic_api_key="fake-claude-key",
        openai_api_key="unused-openai-key",
        _env_file=None,
    )
    monkeypatch.setattr(career, "get_settings", lambda: settings)
    calls = []

    def response(request):
        calls.append(request)
        source = json.loads(json.loads(request.content)["messages"][0]["content"])
        assert source["profile"]["resume_text"] == "Built Python pipelines."
        return httpx.Response(
            200,
            json={
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": draft(kind).model_dump_json()}],
                "usage": {"input_tokens": 123, "output_tokens": 45},
            },
        )

    async def claude(instructions, content, output_type, selected):
        return await anthropic_provider.run_anthropic(
            instructions, content, output_type, selected, transport=httpx.MockTransport(response)
        )

    def no_openai(*args, **kwargs):
        pytest.fail("Selected Claude must never initialize OpenAI")

    monkeypatch.setattr(career, "run_anthropic", claude)
    monkeypatch.setattr(career, "AsyncOpenAI", no_openai)
    job, profile = facts()
    result = asyncio.run(career.generate_career(job, "Acme", profile, kind))
    assert result.provider == "anthropic"
    assert result.model == settings.anthropic_model
    assert result.input_tokens == 123
    assert result.requires_review
    assert result.generated_at is not None
    assert len(calls) == 1


def test_claude_failure_never_falls_back_to_openai(monkeypatch):
    settings = Settings(
        ai_provider="anthropic",
        anthropic_api_key="fake-claude-key",
        openai_api_key="unused-openai-key",
        _env_file=None,
    )
    monkeypatch.setattr(career, "get_settings", lambda: settings)

    async def fail(*args, **kwargs):
        raise RuntimeError("private-claude-diagnostic")

    def no_openai(*args, **kwargs):
        pytest.fail("Claude failure must not initialize OpenAI")

    monkeypatch.setattr(career, "run_anthropic", fail)
    monkeypatch.setattr(career, "AsyncOpenAI", no_openai)
    job, profile = facts()
    with pytest.raises(career.CareerGenerationError) as caught:
        asyncio.run(career.generate_career(job, "Acme", profile, "cover_letter"))
    assert "private-claude" not in str(caught.value)


def test_claude_rejects_invented_evidence(monkeypatch):
    settings = Settings(ai_provider="anthropic", anthropic_api_key="fake-key", _env_file=None)
    monkeypatch.setattr(career, "get_settings", lambda: settings)

    async def claude(*args, **kwargs):
        return draft(quote="Led an invented team."), 10, 10

    monkeypatch.setattr(career, "run_anthropic", claude)
    job, profile = facts()
    with pytest.raises(career.CareerGenerationError, match="evidence"):
        asyncio.run(career.generate_career(job, "Acme", profile, "cover_letter"))


@pytest.mark.parametrize("selected", ["openai", "anthropic"])
def test_common_structured_input_limit_prevents_provider_call(monkeypatch, selected):
    settings = Settings(
        ai_provider=selected,
        openai_api_key="fake-openai",
        anthropic_api_key="fake-claude",
        max_input_chars=1000,
        _env_file=None,
    )
    monkeypatch.setattr(career, "get_settings", lambda: settings)

    def fail(*args, **kwargs):
        pytest.fail("Overlong input must not reach either provider")

    monkeypatch.setattr(career, "run_anthropic", fail)
    monkeypatch.setattr(career, "AsyncOpenAI", fail)
    with pytest.raises(career.CareerInputError, match="limit"):
        asyncio.run(career.run_structured("test", "system", "x" * 1001, JobExtraction))


@pytest.mark.parametrize("selected", ["openai", "anthropic"])
def test_unselected_key_never_dispatches(monkeypatch, selected):
    settings = Settings(
        ai_provider=selected,
        openai_api_key="unselected-key" if selected == "anthropic" else None,
        anthropic_api_key="unselected-key" if selected == "openai" else None,
        _env_file=None,
    )
    monkeypatch.setattr(career, "get_settings", lambda: settings)

    def fail(*args, **kwargs):
        pytest.fail("An unselected credential must not enable provider calls")

    monkeypatch.setattr(career, "run_anthropic", fail)
    monkeypatch.setattr(career, "AsyncOpenAI", fail)
    with pytest.raises(career.AIUnavailable):
        asyncio.run(career.run_structured("test", "system", "posting", JobExtraction))


def test_claude_extraction_uses_selected_model_and_safe_offline_fallback(monkeypatch):
    settings = Settings(
        ai_provider="anthropic",
        anthropic_api_key="fake-claude-key",
        _env_file=None,
    )
    monkeypatch.setattr(career, "get_settings", lambda: settings)
    monkeypatch.setattr(extract, "get_settings", lambda: settings)

    async def success(instructions, content, output_type, selected):
        assert output_type is JobExtraction
        assert "Python" in json.loads(content)["posting"]
        return JobExtraction(company="Acme", title="Engineer", skills=["Python"]), 20, 10

    monkeypatch.setattr(career, "run_anthropic", success)
    captured = extract.extract("Python engineer")
    assert captured.method is ExtractMethod.llm
    assert captured.model == settings.anthropic_model
    assert captured.input_tokens == 20

    async def fail(*args, **kwargs):
        raise RuntimeError("private-claude-response")

    monkeypatch.setattr(career, "run_anthropic", fail)
    fallback = extract.extract("Python engineer")
    assert fallback.method is ExtractMethod.heuristic
    assert fallback.model is None
    assert "anthropic extraction failed" in fallback.error
    assert "private-claude" not in fallback.error


def test_claude_jsonld_still_precedes_paid_extraction(monkeypatch):
    settings = Settings(ai_provider="anthropic", anthropic_api_key="fake-key", _env_file=None)
    monkeypatch.setattr(extract, "get_settings", lambda: settings)

    def fail(*args, **kwargs):
        pytest.fail("JSON-LD must still prevent paid extraction")

    monkeypatch.setattr(extract, "llm_extract", fail)
    assert extract.extract("Posting", html=ARTICLE).method is ExtractMethod.jsonld


def test_older_career_results_default_to_openai():
    result = career.CareerResult(kind="cover_letter", model="old-model", draft=draft())
    assert result.provider == "openai"


def test_openai_official_endpoint_ignores_ambient_override(configured, monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://evil.invalid/v1")
    actual_client = career.AsyncOpenAI
    observed = []

    def client(**kwargs):
        assert kwargs["base_url"] == "https://api.openai.com/v1"
        assert kwargs["http_client"]._trust_env is False
        assert kwargs["http_client"].follow_redirects is False
        assert kwargs["max_retries"] == 0
        observed.append(kwargs)
        return actual_client(**kwargs)

    async def run(*args, **kwargs):
        return fake_result(draft())

    monkeypatch.setattr(career, "AsyncOpenAI", client)
    monkeypatch.setattr(career.Runner, "run", run)
    job, profile = facts()
    assert (
        asyncio.run(career.generate_career(job, "Acme", profile, "cover_letter")).provider
        == "openai"
    )
    assert len(observed) == 1


@pytest.mark.parametrize("posting", ["a" * 2000, '"\\' * 1000, "漢字" * 1000])
def test_extraction_json_overhead_is_inside_input_budget(monkeypatch, posting):
    settings = Settings(
        ai_provider="openai",
        openai_api_key="fake-key",
        max_input_chars=1000,
        _env_file=None,
    )
    monkeypatch.setattr(extract, "get_settings", lambda: settings)

    async def capture(name, instructions, content, output_type):
        assert len(content) <= settings.max_input_chars
        source = json.loads(content)
        assert source["posting"]
        assert posting.startswith(source["posting"])
        assert len(source["hint"]) <= 200
        return JobExtraction(company="Acme", title="Engineer"), 10, 10

    monkeypatch.setattr(extract, "run_structured", capture)
    assert extract.llm_extract(posting, hint="h" * 5000)[1:] == (10, 10)
