# Canonical discovery and concurrent capture

Design reviewed against current source; implementation has not started. Direct
extension authorization currently owns the next additive migration. This work
follows it and does not replace the existing unchanged-posting preservation path.

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

Reserve a short, fenced capture lease before extraction under the existing owner
lock. Unsupported URL captures can use an exact URL digest; text-only captures
remain distinct. A competing capture receives a conflict without dispatching a
provider request. Release the database transaction during extraction.

On completion, reacquire the owner lock and check lease nonce, deadline and job
baseline before atomically saving the result and identity mapping. Expired lease
takeover uses a new nonce so a late worker cannot overwrite newer data. Failure
and cancellation release only the worker's own lease. Do not automatically retry
provider calls or claim exactly-once billing after a crash or ambiguous timeout.

Explicit job deletion removes that job's mappings and reservations. Unchanged
captures continue preserving pipeline state, notes and saved drafts. Older live
images bypass a newly introduced reservation protocol, so deployment must account
for all active writers before claiming cross-instance concurrency protection.

## Acceptance

Exercise simultaneous alias captures on SQLite and PostgreSQL: one extraction,
one job, preserved related records. Cover stale-worker fencing, changed input,
legacy ambiguity, cancellation and backup compatibility. Freeze the preceding
schema for installed backups before adding the next migration.

Discovery freshness is a separate remaining task. An identity or timestamp alone
does not prove that a posting is still available.
