"""Insert reviewed proxy leads into Jobbr without changing the source or existing jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from .db import get_engine
from .models import Application, Company, Job, JobStatus, Stage, pk


def reviewed_leads(source: Path) -> list[dict[str, Any]]:
    if not source.is_file():
        raise ValueError("Proxy database must already exist.")
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        # Only explicitly reviewed signals; do not import classifier candidates or private bodies.
        return [
            dict(row)
            for row in connection.execute(
                "SELECT s.id, s.conversation_id, s.role_title, s.summary, s.received_at, "
                "c.name AS company_name, p.full_name AS contact_name, "
                "p.primary_profile_url AS contact_url FROM recruiter_signal s "
                "LEFT JOIN company c ON c.id=s.hiring_company_id "
                "LEFT JOIN person p ON p.id=s.recruiter_person_id "
                "WHERE s.state='reviewing' ORDER BY s.id LIMIT 1000"
            )
        ]


def import_leads(
    session: Session, leads: list[dict[str, Any]], *, apply: bool = False
) -> dict[str, int]:
    counts = {"reviewed": len(leads), "created": 0, "existing": 0}
    # Validate the complete input before changing any destination rows.
    for lead in leads:
        if not isinstance(lead.get("id"), str) or not lead["id"].startswith("sig_"):
            raise ValueError("Invalid proxy signal ID.")
        if lead.get("received_at"):
            datetime.fromisoformat(lead["received_at"].replace("Z", "+00:00"))
    for lead in leads:
        source_key = hashlib.sha256(("jobsearch-proxy:" + lead["id"]).encode()).hexdigest()
        if session.exec(select(Job).where(Job.content_hash == source_key)).first():
            counts["existing"] += 1
            continue
        counts["created"] += 1
        if not apply:
            continue
        company_name = lead.get("company_name") or "Unknown employer"
        company = session.exec(select(Company).where(Company.name == company_name)).first()
        if company is None:
            company = Company(name=company_name)
            session.add(company)
            session.flush()
        evidence = {
            "source": "linkedin_export",
            "proxy_signal_id": lead["id"],
            "proxy_conversation_id": lead.get("conversation_id"),
            "outreach_received_at": lead.get("received_at"),
            "contact_name": lead.get("contact_name"),
            "contact_url": lead.get("contact_url"),
            "summary": lead.get("summary"),
            "opening_verified": False,
        }
        now = datetime.now(UTC).replace(tzinfo=None)
        job = Job(
            company_id=pk(company),
            title=lead.get("role_title") or "Recruiting lead (title not supplied)",
            status=JobStatus.unknown,
            summary=lead.get("summary"),
            content_hash=source_key,
            raw_text=json.dumps(evidence, ensure_ascii=False),
            # A message date is not a posting/discovery/refresh date.
            posted_at=None,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(job)
        session.flush()
        notes = (
            f"LinkedIn recruiter lead; opening not independently verified.\n"
            f"Contact: {lead.get('contact_name') or 'Unknown'}\n"
            f"Profile: {lead.get('contact_url') or 'Unknown'}\n"
            f"Outreach: {lead.get('received_at') or 'Unknown'}\n"
            f"Source signal: {lead['id']}\n"
            f"Source conversation: {lead.get('conversation_id') or 'Unknown'}\n\n"
            f"{lead.get('summary') or ''}"
        )
        session.add(Application(job_id=pk(job), stage=Stage.saved, notes=notes))
    if apply:
        session.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proxy-db", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Default is a read-only preview.")
    args = parser.parse_args()
    with Session(get_engine()) as session:
        print(json.dumps(import_leads(session, reviewed_leads(args.proxy_db), apply=args.apply)))


if __name__ == "__main__":
    main()
