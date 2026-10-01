"""Row → JSON-ready dicts for the API."""

from typing import Any

from .models import Stage
from .repo import JobRow

Json = dict[str, Any]


def job_out(row: JobRow, detail: bool = False) -> Json:
    d = row.job.model_dump(exclude=None if detail else {"raw_text"})
    d["company"] = row.company.model_dump(include={"id", "name", "domain", "industry"})
    d["match"] = row.match.model_dump(exclude={"id", "job_id", "profile_id"}) if row.match else None
    d["application"] = (
        row.application.model_dump(exclude={"id", "job_id"})
        if row.application
        else {"stage": Stage.saved, "notes": ""}
    )
    return d
