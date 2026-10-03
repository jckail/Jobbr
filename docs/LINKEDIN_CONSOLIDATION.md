# LinkedIn workflow consolidated under Jobbr

Jobbr is the job-search shortlist and pipeline. The companion
[jobsearchProxyApp](https://github.com/jckail/jobsearchProxyApp) retains the personal
message/contact evidence graph and official LinkedIn export importer. These are
two storage domains in one workflow, not interchangeable database schemas.

The reviewed-lead bridge and authenticated MCP interface use the current v2 data
layer on `main`. The original prototype files remain separate from these entrypoints.

## Data boundary

`python -m jobbr.proxy_import --proxy-db PATH` previews reviewed signals. Add
`--apply` to insert them as Saved Jobbr entries. The source opens read-only and
only `reviewing` signals are eligible. The bridge does not copy private message
bodies, emails, phone numbers, raw exports, classifier candidates or connection
lists. Contact names/profile URLs, outreach time, source IDs and the curated
review summary stay attached in shortlist notes and a provenance envelope. The
review summary is not copied into ordinary role context; MCP shortlist permission
is required to read it. The current source query is limited to the first 1,000
reviewed signals by ID and has no cursor; larger archives need a pagination extension
before claiming complete coverage.

All new roles have unknown opening status. Posting date stays unknown; Jobbr
discovery time is separate from the retained original outreach date. Unknown
employers and titles remain explicitly unknown. Compensation is retained in the
review summary rather than converted into annual pay without evidence. A stable
source-signal hash prevents duplicates. Existing records, notes and pipeline
stages are never replaced on subsequent imports. Later source corrections require
explicit review; this bridge is insert-only, not an automatic refresh service.
Re-extraction rejects these evidence envelopes before calling a provider; add a
verified job posting separately when one becomes available.

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

## Verification

Synthetic tests cover preview behavior, a read-only source, exclusion of unreviewed
signals, repeat-import deduplication, preservation of edited application stages
and notes, invalid-batch rejection, and unknown employer/title data. These tests
do not access a live archive or import personal records. Review and back up the
intended destination before an actual import.
