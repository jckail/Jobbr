"""HTML → clean text, schema.org JobPosting extraction, and a heuristic fallback extractor."""

import json
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

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
        except (json.JSONDecodeError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, dict):
                if "@graph" in d:
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
        org = d.get("hiringOrganization") or {}
        company = org.get("name") if isinstance(org, dict) else str(org)
        desc_html = d.get("description") or ""
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
                cmin, cmax = v.get("minValue") or v.get("value"), v.get("maxValue") or v.get("value")
                period = str(v.get("unitText", "YEAR")).upper()
            cur = base.get("currency") or "USD"
        else:
            cur = "USD"
        mult = PERIOD.get(period, 1)
        remote = "remote" if d.get("jobLocationType") == "TELECOMMUTE" else "unknown"
        skills = find_skills(f"{d.get('title','')} {desc_text} {d.get('skills','')}")
        return JobExtraction(
            company=company or "Unknown",
            title=d.get("title") or "Untitled",
            employment_type=(
                ", ".join(d["employmentType"]) if isinstance(d.get("employmentType"), list)
                else d.get("employmentType")
            ),
            remote_policy=remote,
            locations=locs,
            comp_min=int(float(cmin) * mult) if cmin else None,
            comp_max=int(float(cmax) * mult) if cmax else None,
            comp_currency=cur,
            summary=desc_text[:400] or None,
            responsibilities=_listify(desc_html)[:10],
            skills=skills,
            posted_at=d.get("datePosted"),
        )
    return None


_COMP = re.compile(r"\$\s?(\d{2,3}(?:,\d{3})|\d{2,3}\s?[kK])\s*(?:-|–|—|to)\s*\$?\s?(\d{2,3}(?:,\d{3})|\d{2,3}\s?[kK])")
_YOE = re.compile(r"(\d{1,2})\s*\+?\s*(?:years|yrs)", re.IGNORECASE)


def _money(s: str) -> int:
    s = s.replace(",", "").replace(" ", "").lower()
    return int(s[:-1]) * 1000 if s.endswith("k") else int(s)


def heuristic_job(text: str, title_hint: str | None = None, company_hint: str | None = None) -> JobExtraction:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = title_hint or (lines[0][:120] if lines else "Untitled role")
    low = text.lower()
    remote = (
        "hybrid" if "hybrid" in low
        else "remote" if re.search(r"\bremote\b", low)
        else "onsite" if re.search(r"on-?site|in[- ]office", low)
        else "unknown"
    )
    m = _COMP.search(text)
    cmin, cmax = (_money(m.group(1)), _money(m.group(2))) if m else (None, None)
    yoe = [int(x) for x in _YOE.findall(text)]
    bullets = [ln.lstrip("•-*· ").strip() for ln in lines if ln[:1] in "•-*·" and 15 < len(ln) < 220]
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
        return datetime.fromisoformat(s).replace(tzinfo=None)
    except ValueError:
        return None
