"""Transparent, deterministic fit scoring. Every point is explainable in `breakdown`."""

from .models import Job, Match, Profile, RemotePolicy, Seniority

WEIGHTS = {"skills": 55, "seniority": 15, "location": 15, "comp": 15}
LADDER = [Seniority.intern, Seniority.junior, Seniority.mid, Seniority.senior, Seniority.staff,
          Seniority.principal]
RANK = {s: i for i, s in enumerate(LADDER)}


def _skills(job: Job, profile: Profile) -> tuple[float, list[str], list[str]]:
    have = set(profile.skills)
    req = list(dict.fromkeys(job.skills))
    nice = [s for s in job.nice_to_have if s not in req]
    if not req and not nice:
        return 0.5, [], []  # nothing to compare: neutral
    total = len(req) * 1.0 + len(nice) * 0.4
    got = sum(1.0 for s in req if s in have) + sum(0.4 for s in nice if s in have)
    matched = [s for s in req + nice if s in have]
    missing = [s for s in req if s not in have]
    return got / total, matched, missing


def _seniority(job: Job, profile: Profile) -> float:
    a, b = RANK.get(job.seniority), RANK.get(profile.seniority)
    if a is None or b is None:
        return 0.7  # unknown on either side
    return {0: 1.0, 1: 0.6, -1: 0.8}.get(a - b, 0.2 if a > b else 0.5)  # stretching up is OK


def _location(job: Job, profile: Profile) -> float:
    pref = profile.remote_pref
    if pref == RemotePolicy.unknown or job.remote_policy == RemotePolicy.unknown:
        return 0.7
    if job.remote_policy == RemotePolicy.remote:
        return 1.0 if pref in (RemotePolicy.remote, RemotePolicy.hybrid) else 0.8
    if pref == RemotePolicy.remote:
        return 0.15
    if profile.locations and any(
        p.lower().split(",")[0] in loc.lower() for p in profile.locations for loc in job.locations
    ):
        return 1.0
    return 0.4 if profile.locations else 0.7


def _comp(job: Job, profile: Profile) -> float:
    if not profile.min_comp:
        return 0.7
    top = job.comp_max or job.comp_min
    if not top:
        return 0.5
    return 1.0 if top >= profile.min_comp else max(0.0, 1 - (profile.min_comp - top) / profile.min_comp * 3)


def score(job: Job, profile: Profile) -> Match:
    sk, matched, missing = _skills(job, profile)
    parts = {"skills": sk, "seniority": _seniority(job, profile),
             "location": _location(job, profile), "comp": _comp(job, profile)}
    total = round(sum(parts[k] * w for k, w in WEIGHTS.items()))
    breakdown = {k: {"score": round(v * 100), "weight": WEIGHTS[k]} for k, v in parts.items()}
    bits = []
    if matched:
        bits.append(f"You cover {len(matched)} of its skills ({', '.join(matched[:4])}).")
    if missing:
        bits.append(f"Gaps: {', '.join(missing[:4])}.")
    return Match(job_id=job.id, profile_id=profile.id, score=total, breakdown=breakdown,
                 matched_skills=matched, missing_skills=missing, rationale=" ".join(bits) or None)
