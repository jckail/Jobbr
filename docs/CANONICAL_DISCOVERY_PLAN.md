# Canonical discovery and concurrent capture

Source implementation is ready for integration verification in the isolated
discovery-identity worktree. Migration 0007 follows direct extension authorization
at revision 0006. The existing unchanged-posting preservation path remains, with
an additional fix for identical pasted postings longer than the stored prefix.

## Identity

Derive identity server-side only for validated HTTPS Greenhouse and Lever URLs
with known board and posting-ID paths. Ignore query strings and fragments only
for these recognized identities. Preserve board and posting-ID case and reject
ambiguous encoded paths. Do not infer equivalence for custom domains or trust a
client-supplied provider identity.

Add a separate unique provider/board/posting-ID mapping to a job. The migration
creates empty mapping tables: it must not rewrite existing URLs, make Job.url
unique, merge jobs or delete duplicates. Adopt legacy records lazily only when
a bounded lookup finds exactly one matching job; ambiguity or lookup overflow
requires an actionable conflict response.

## Concurrent extraction

Reserve a fenced capture lease before extraction under the existing owner
lock. Unsupported URL captures can use an exact URL digest; text-only captures
remain distinct. A competing capture receives a conflict without dispatching a
provider request. Release the database transaction during extraction.

On completion, reacquire the owner lock and check lease nonce, deadline and job
baseline before atomically saving the result and identity mapping. Leases last
at most 300 seconds, with a shared cap of 128. Legacy lookup scans at most 1000
candidates for the requested posting, rather than unrelated provider jobs.
Expired lease
takeover uses a new nonce so a late worker cannot overwrite newer data. Failure
and cancellation release only the worker's own lease. Do not automatically retry
provider calls or claim exactly-once billing after a crash or ambiguous timeout.
Expiry takeover can dispatch another provider call while an old worker is still
running; fencing prevents its late database write, not the remote charge.

Explicit re-extraction uses the same reservation and baseline checks. It cannot
silently replace newer posting details after starting from older stored text.

Explicit job deletion removes that job's mappings and reservations. Unchanged
captures continue preserving pipeline state, notes and saved drafts. Older live
images bypass a newly introduced reservation protocol, so deployment must account
for all active writers before claiming cross-instance concurrency protection.

## Acceptance

Exercise simultaneous alias captures on SQLite and PostgreSQL: one extraction,
one job, preserved related records. Cover stale-worker fencing, changed input,
legacy ambiguity, cancellation and backup compatibility. Freeze the preceding
schema for installed backups before adding the next migration.

Focused verification passed 25 identity/repository cases, 34 migration/backup
cases, and four root-selected SQLite orchestration cases. PostgreSQL and the
mandatory combined gate remain pending. No canonical source has been published.

Discovery freshness is a separate remaining task. An identity or timestamp alone
does not prove that a posting is still available.

## Next increment: explicit availability observations

Source review found that current discovery snapshots expose `fetched_at` and
`truncated`, while failures are fetch errors rather than posting availability.
Filtered searches, the first-100 window and rejected links cannot prove a saved
posting disappeared. An explicit transient observation is now implemented; combined verification and browser acceptance remain pending.

A bounded next step is a private, explicit `Check availability` action on a saved
job. Resolve the identity from server-owned mapping or a recognized saved URL,
then fetch one fixed vendor board through the existing hardened transport.
Return a transient observation with `checked_at`, a checked source URL, a fixed
reason and one of these states:

- Available: the target identity was listed when checked; this does not certify
  the employer is still hiring.
- Unavailable: the target is absent from a proven complete, valid, unfiltered
  board response. Vendor completeness semantics must be verified first.
- Unknown: truncated/partial snapshots, malformed or skipped data, unsupported
  identity, timeout, 403/429/5xx or a board-level 404.

Keep this read-only: no migration, provider dispatch, automatic closing, deletion
or application/draft changes. Use checked-snapshot wording in discovery instead
of implying current availability. A short response alone does not prove board
completeness. Tests should cover disappearance from a complete board, first-100
misses, outages/404s, alias identity, private access and unchanged saved history.


### Implementation verification checkpoint

`POST /api/jobs/{id}/availability` requires an owner session and CSRF, or a
configured instance token. Unsecured demo instances cannot initiate this check.
The service resolves only server-owned identity, releases its read transaction,
and performs one deadline-bounded board fetch using a shared four-worker limiter.
Observations do not persist or alter application state. Greenhouse absence
requires explicit `meta.total` equality and a fully validated board within the
100-row bound; Lever absence remains unknown. A valid target in the inspected
window can establish listed status even when the board is larger.

Vendor semantics were checked against the official
[Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html#list-jobs)
and [Lever postings API](https://github.com/lever/postings-api#get-a-list-of-job-postings).
Focused checks passed 59 discovery cases, seven API cases with one PostgreSQL
skip, and strict mypy across the four affected backend modules. The UI has
explicit checking, retry and timestamp states; web/full gate and real browser
acceptance remain unverified. Source-independent Graphify results lacked Jobbr
coverage; live source and dependency-free Codemogger text retrieval were used.
