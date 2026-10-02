"""Dashboard aggregates, computed from already-loaded rows."""

from collections import Counter
from datetime import timedelta
from statistics import median
from typing import Any

from .models import Profile, Stage, utcnow
from .repo import JobRow

DAYS = 14
BUCKET = 20


def _score_buckets(scores: list[int]) -> list[dict[str, Any]]:
    out = []
    for lo in range(0, 100, BUCKET):
        last = lo + BUCKET >= 100  # the top bucket includes a perfect 100
        n = sum(lo <= x < lo + BUCKET or (last and x == 100) for x in scores)
        out.append({"label": f"{lo}-{lo + BUCKET - 1}", "count": n})
    return out


def _added_per_day(rows: list[JobRow]) -> list[dict[str, Any]]:
    since = utcnow() - timedelta(days=DAYS - 1)
    counts = Counter(
        r.job.first_seen_at.date().isoformat() for r in rows if r.job.first_seen_at >= since
    )
    days = [(since + timedelta(days=i)).date().isoformat() for i in range(DAYS)]
    return [{"day": d, "count": counts.get(d, 0)} for d in days]


def compute(rows: list[JobRow], profile: Profile, ai_cost_usd: float) -> dict[str, Any]:
    stages = Counter(r.stage for r in rows)
    demand = Counter(skill for r in rows for skill in r.job.skills)
    have = set(profile.skills)
    scores = [r.score for r in rows if r.score is not None]
    comps = [
        (r.job.comp_min + r.job.comp_max) / 2
        for r in rows
        if r.job.comp_currency.upper() == "USD"
        and r.job.comp_min is not None
        and r.job.comp_max is not None
    ]
    top = sorted(rows, key=lambda r: -(r.score if r.score is not None else -1))[:5]
    return {
        "totals": {
            "jobs": len(rows),
            "companies": len({r.company.id for r in rows}),
            "avg_score": round(sum(scores) / len(scores)) if scores else None,
            "median_comp": median(comps) if comps else None,
            "ai_cost_usd": round(ai_cost_usd, 4),
        },
        "stages": {st.value: stages.get(st, 0) for st in Stage},
        "skill_demand": [
            {"skill": k, "jobs": v, "have": k in have} for k, v in demand.most_common(12)
        ],
        "added_per_day": _added_per_day(rows),
        "score_buckets": _score_buckets(scores),
        "top_matches": [
            {"id": r.job.id, "title": r.job.title, "company": r.company.name, "score": r.score}
            for r in top
        ],
    }
