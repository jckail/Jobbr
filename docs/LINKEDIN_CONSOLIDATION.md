# LinkedIn workflow consolidated under Jobbr

Jobbr is the job-search shortlist and pipeline. The companion
[jobsearchProxyApp](https://github.com/jckail/jobsearchProxyApp) retains the personal
message/contact evidence graph and official LinkedIn export importer. These are
two storage domains in one workflow, not interchangeable database schemas.

The `feat/linkedin-consolidation` branch includes the authenticated Jobbr MCP work
from `feat/jobbr-mcp-v2` and the reviewed-lead bridge. The legacy `main` prototype
and dirty legacy checkouts are not the integration target.

## Data boundary

`python -m jobbr.proxy_import --proxy-db PATH` previews reviewed signals. Add
`--apply` to insert them as Saved Jobbr entries. The source opens read-only and
only `reviewing` signals are eligible. The bridge does not copy private message
bodies, emails, phone numbers, raw exports, classifier candidates or connection
lists. Contact names/profile URLs, outreach time, source IDs and the curated
review summary stay attached in shortlist notes and a provenance envelope.

All new roles have unknown opening status. Posting date stays unknown; Jobbr
discovery time is separate from the retained original outreach date. Unknown
employers and titles remain explicitly unknown. Compensation is retained in the
review summary rather than converted into annual pay without evidence. A stable
source-signal hash prevents duplicates. Existing records, notes and pipeline
stages are never replaced on subsequent imports. Later source corrections require
explicit review; this bridge is insert-only, not an automatic refresh service.

## Existing local Docker installations

The one-shot `compose.proxy-import.yaml` joins the existing volumes. It mounts the
proxy volume read-only, uses the existing `jobbr:local` runtime, and has no network.
It neither rebuilds nor restarts either application. Override `JOBBR_PROXY_VOLUME`
and `JOBBR_DATA_VOLUME` only when intentionally targeting another installation.

```sh
docker compose -f compose.proxy-import.yaml run --rm import
# First take a consistent Jobbr backup using docs/BACKUP.md, then:
docker compose -f compose.proxy-import.yaml run --rm import --proxy-db /proxy/graph.db --apply
```

Use the existing owner-private Jobbr instance for real data. The verified local
installation binds to `127.0.0.1:8000`; do not expose it publicly without enabling
and testing its access controls. The source proxy remains the MCP surface for
messages, contacts, evidence review and export ingestion. Jobbr MCP serves its
role/company/shortlist domain; see [MCP.md](MCP.md). Its external OAuth provider,
client/owner binding, deployment and real ChatGPT connection remain separate
setup work. A code branch is not proof of a live authenticated connection.

## Verified local milestone, 2026-10-02

The real local run backed up Jobbr consistently, imported seven reviewed leads
into seven Saved entries, then previewed again: zero new entries and seven
existing entries. All seven retain unknown opening status and no posting date.
Focused synthetic tests cover preview behavior, repeat-import deduplication,
preservation of edited application stages/notes, and unknown employer/title data.
No private data is committed. The older LinkedIn export's message/contact counts
are snapshot counts; newer messages require another official export while live
LinkedIn capture is disabled.
