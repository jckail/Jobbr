import pytest

from jobbr import matching, parsing, safefetch
from jobbr.models import Job, Profile, RemotePolicy, Seniority
from jobbr.skills import find_skills, normalize_skill
from tests.conftest import ARTICLE, reset_settings


def make_job(**kw) -> Job:
    base = {"id": 1, "company_id": 1, "title": "Eng", "skills": ["python", "sql"]}
    return Job(**{**base, **kw})


def make_profile(**kw) -> Profile:
    base = {"id": 1, "skills": ["python"], "seniority": Seniority.senior}
    return Profile(**{**base, **kw})


class TestSkills:
    def test_finds_aliases(self):
        assert {"python", "kubernetes", "react", "go"} <= set(
            find_skills("Python, Go, k8s, React.js")
        )

    def test_ambiguous_words_need_list_context(self):
        assert "go" not in find_skills("we go further than anyone")
        assert "r" not in find_skills("R&D and more")

    def test_normalize(self):
        assert normalize_skill("  PostgreSQL ") == "postgres"
        assert normalize_skill("Some Unknown Tool") == "some unknown tool"


class TestParsing:
    def test_jsonld_annualises_hourly_pay(self):
        job = parsing.jsonld_job(ARTICLE)
        assert job is not None
        assert job.company == "Acme"
        assert job.remote_policy == RemotePolicy.remote
        assert (job.comp_min, job.comp_max) == (90 * 2080, 120 * 2080)
        assert "kafka" in job.skills

    def test_jsonld_absent(self):
        assert parsing.jsonld_job("<html><body>nothing</body></html>") is None

    def test_heuristics(self):
        job = parsing.heuristic_job("Eng\nRemote role. $150k - $190k. 5+ years of Python.")
        assert (job.comp_min, job.comp_max, job.years_experience_min) == (150_000, 190_000, 5)
        assert job.remote_policy == RemotePolicy.remote

    def test_html_to_text_strips_noise(self):
        text = parsing.html_to_text("<body><nav>menu</nav><script>x()</script><main>Hello</main>")
        assert text == "Hello"


class TestSafeFetch:
    @pytest.mark.parametrize(
        "url", ["http://127.0.0.1:8000/x", "http://10.0.0.5/", "file:///etc/passwd"]
    )
    def test_blocks_private_and_non_http(self, env, url):
        env.setenv("JOBBR_ALLOW_PRIVATE_FETCH", "0")
        reset_settings()
        with pytest.raises(safefetch.FetchError):
            safefetch.assert_public_url(url)


class TestMatching:
    def test_full_skill_overlap_scores_high(self):
        m = matching.score(make_job(), make_profile(skills=["python", "sql"]))
        assert m.score >= 85
        assert m.missing_skills == []

    def test_gaps_are_reported(self):
        m = matching.score(make_job(), make_profile())
        assert m.missing_skills == ["sql"]
        assert m.matched_skills == ["python"]
        assert m.breakdown["skills"]["score"] == 50

    def test_remote_only_candidate_penalises_onsite(self):
        job = make_job(remote_policy=RemotePolicy.onsite)
        remote = matching.score(job, make_profile(remote_pref=RemotePolicy.remote))
        assert remote.breakdown["location"]["score"] < 30

    def test_pay_below_floor_scores_lower(self):
        job = make_job(comp_min=80_000, comp_max=100_000)
        low = matching.score(job, make_profile(min_comp=200_000))
        ok = matching.score(job, make_profile(min_comp=90_000))
        assert low.breakdown["comp"]["score"] < ok.breakdown["comp"]["score"] == 100

    def test_no_requirements_is_neutral(self):
        m = matching.score(make_job(skills=[]), make_profile())
        assert m.breakdown["skills"]["score"] == 50
