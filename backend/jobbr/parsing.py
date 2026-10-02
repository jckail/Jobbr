"""HTML → clean text, schema.org JobPosting extraction, and a heuristic fallback extractor."""

import json
import math
import re
from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup

from .models import RemotePolicy
from .schemas import JobExtraction
from .skills import find_skills, normalize_skills

NOISE_TAGS = ["script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"]


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(NOISE_TAGS):
        t.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    text = root.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text)


def _jsonld_blocks(soup: BeautifulSoup) -> list[Any]:
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError, RecursionError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, dict):
                if isinstance(d.get("@graph"), list):
                    stack.extend(d["@graph"])
                out.append(d)
    return out


def _listify(html_or_text: str | None) -> list[str]:
    if not html_or_text:
        return []
    s = BeautifulSoup(html_or_text, "lxml")
    items = [li.get_text(" ", strip=True) for li in s.find_all("li")]
    return [i for i in items if i][:25]


PERIOD = {"YEAR": 1, "MONTH": 12, "WEEK": 52, "DAY": 260, "HOUR": 2080}


def jsonld_job(html: str) -> JobExtraction | None:
    soup = BeautifulSoup(html, "lxml")
    for d in _jsonld_blocks(soup):
        t = d.get("@type")
        if t != "JobPosting" and not (isinstance(t, list) and "JobPosting" in t):
            continue
        try:
            return _jsonld_posting(d)
        except (ValueError, TypeError, OverflowError, AttributeError, RecursionError):
            # A bad block must not prevent another block or plain-text fallback.
            continue
    return None


def _annual_pay(value: Any, multiplier: int) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("Invalid salary")
    annual = float(value) * multiplier
    if not math.isfinite(annual) or not 0 <= annual <= 1_000_000_000:
        raise ValueError("Invalid salary")
    return int(annual)


def _jsonld_posting(d: dict[str, Any]) -> JobExtraction:
    org = d.get("hiringOrganization") or {}
    company = org.get("name") if isinstance(org, dict) else str(org)
    # Reject non-text metadata before BeautifulSoup; parser errors differ by Python version.
    desc_html = d.get("description")
    if desc_html is None:
        desc_html = ""
    elif not isinstance(desc_html, str):
        raise TypeError("Invalid posting description")
    desc_text = BeautifulSoup(desc_html, "lxml").get_text(" ", strip=True)
    locs: list[str] = []
    jl = d.get("jobLocation") or []
    for loc in jl if isinstance(jl, list) else [jl]:
        a = (loc or {}).get("address", {}) if isinstance(loc, dict) else {}
        if isinstance(a, dict):
            bits = [a.get("addressLocality"), a.get("addressRegion"), a.get("addressCountry")]
            s = ", ".join(str(b if not isinstance(b, dict) else b.get("name")) for b in bits if b)
            if s:
                locs.append(s)
    cmin = cmax = None
    period = "YEAR"
    base = d.get("baseSalary")
    if isinstance(base, dict):
        v = base.get("value", {})
        if isinstance(v, dict):
            cmin, cmax = (
                v.get("minValue", v.get("value")),
                v.get("maxValue", v.get("value")),
            )
            period = str(v.get("unitText", "YEAR")).upper()
        cur = base.get("currency") or "USD"
    else:
        cur = "USD"
    mult = PERIOD.get(period, 1)
    remote = (
        RemotePolicy.remote if d.get("jobLocationType") == "TELECOMMUTE" else RemotePolicy.unknown
    )
    skills = find_skills(f"{d.get('title', '')} {desc_text} {d.get('skills', '')}")
    return JobExtraction(
        company=company or "Unknown",
        title=d.get("title") or "Untitled",
        employment_type=(
            ", ".join(d["employmentType"])
            if isinstance(d.get("employmentType"), list)
            else d.get("employmentType")
        ),
        remote_policy=remote,
        locations=locs,
        comp_min=_annual_pay(cmin, mult),
        comp_max=_annual_pay(cmax, mult),
        comp_currency=cur,
        summary=desc_text[:400] or None,
        responsibilities=_listify(desc_html)[:10],
        skills=skills,
        posted_at=d.get("datePosted"),
    )


_AMOUNT = r"(\d{2,3}(?:,\d{3})|\d{2,3}\s?[kK])"
_COMP = re.compile(rf"\$\s?{_AMOUNT}\s*(?:-|\u2013|\u2014|to)\s*\$?\s?{_AMOUNT}")
_YOE = re.compile(r"(\d{1,2})\s*\+?\s*(?:years|yrs)", re.IGNORECASE)


def _money(s: str) -> int:
    s = s.replace(",", "").replace(" ", "").lower()
    return int(s[:-1]) * 1000 if s.endswith("k") else int(s)


def heuristic_job(
    text: str, title_hint: str | None = None, company_hint: str | None = None
) -> JobExtraction:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = title_hint or (lines[0][:120] if lines else "Untitled role")
    low = text.lower()
    if "hybrid" in low:
        remote = RemotePolicy.hybrid
    elif re.search(r"\bremote\b", low):
        remote = RemotePolicy.remote
    elif re.search(r"on-?site|in[- ]office", low):
        remote = RemotePolicy.onsite
    else:
        remote = RemotePolicy.unknown
    m = _COMP.search(text)
    cmin, cmax = (_money(m.group(1)), _money(m.group(2))) if m else (None, None)
    yoe = [int(x) for x in _YOE.findall(text)]
    bullets = [
        ln.lstrip("•-*· ").strip() for ln in lines if ln[:1] in "•-*·" and 15 < len(ln) < 220
    ]
    return JobExtraction(
        company=company_hint or "Unknown",
        title=title,
        remote_policy=remote,
        comp_min=cmin,
        comp_max=cmax,
        years_experience_min=min(yoe) if yoe else None,
        summary=" ".join(lines[1:4])[:300] if len(lines) > 1 else None,
        responsibilities=bullets[:8],
        qualifications=bullets[8:16],
        skills=normalize_skills(find_skills(text)),
    )


def parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        parsed = datetime.fromisoformat(s)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC)
    return parsed.replace(tzinfo=None)
