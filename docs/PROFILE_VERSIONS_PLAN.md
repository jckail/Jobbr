# Profile revisions and resume tailoring: source review

Reviewed against the current source after the verified discovery increment f57b31e. Immutable profile history is published and verified locally; tailoring and generation provenance are implemented with passing mandatory local checks, while browser/live-provider acceptance remains pending. Keep the existing active Profile row and IDs so current scoring, application history and API clients remain compatible.

## Immutable profile history (implemented foundation)

Add owner-scoped, bounded immutable profile revisions with a saved timestamp, content fingerprint and every profile scoring field; the initial interface labels revisions by timestamp and ID. Explicit profile save creates a revision transactionally; identical content may reuse the current revision. Explicit activation restores the selected snapshot and re-scores jobs. Expected revision checks reject stale concurrent saves/activation with409. Backfill an initial revision from the existing profile without inventing an original creation date.

Revision list/detail/activation/deletion must use the stronger private draft access gate, because public demo profile reads do not justify exposing historical resumes. Define count/content limits and referenced-revision deletion behavior. Document that backups retain historical resume text. PDF previews must stay transient and create no revision until an explicit save.

## Generation and review (implemented; acceptance gates remain)

Add a separate tailoring schema/endpoint that receives an explicit revision ID and job ID. Reuse existing OpenAI/Claude dispatch and evidence validation. Return proposed resume text, evidence-backed changes, unresolved gaps and source provenance captured before generation: revision ID and job-input fingerprint.

Generation is transient. Saving reviewed text and explicitly accepting it as a new active profile revision are separate actions. Edited saved results are reviewed user content; do not imply the server certified every edited claim. Existing drafts retain unknown revision provenance. Current saved draft fingerprints are computed from mutable sources at save time; that is insufficient to identify earlier generation inputs.

## Migration and acceptance requirements

Migration0004 is implemented with frozen0003 backup verification alongside0001/0002. For the tailoring increment, freeze/register0004 before adding additive0005. Preserve existing profile IDs and old saved draft JSON. Verify SQLite and PostgreSQL upgrade plus restore of old and new backups.

The central acceptance scenario: generate from revisionA, activateB while generation runs, then save the result. The saved result must remain bound toA; saving must not activateA, overwriteB, or recompute provenance fromB. Also prove explicit restore/re-scoring, stale-save rejection, private access to history, bounded history/content, referenced revision deletion behavior, invented-evidence rejection and PDF preview creating no revision.

Sources: backend/jobbr/models.py, services.py, career.py, drafts.py, api.py; backend/migrations; scripts/backup.py; docs/RESUME.md and ROADMAP.md. History foundation passed mandatory local verification, including PostgreSQL concurrency and historical/current backups. The tailoring portion now passes mandatory local checks; actual browser and paid-provider acceptance remain separate gates. No credential, paid provider, cloud or routing action is authorized by this plan.

## Tailoring contract agreed for implementation (October 2)

This contract is implemented with passing focused and mandatory local checks; publication, browser and live-provider acceptance are tracked in PROGRESS.md. Generate from an explicit source_revision_id at POST /jobs/{job_id}/tailoring. Capture the immutable revision, selected provider settings and bounded exact job/candidate input before awaiting generation; reject an oversized complete-resume envelope instead of silently tailoring a truncated resume. Return proposed resume text, evidence-backed changes, gaps, review notes and an opaque receipt_id. Quote matching validates cited source text, not every generated claim; human review remains required.

The receipt contains server-captured provenance metadata only: owner/revision/job IDs and hashes, exact input hash, provider/model, generation time, usage and original-result hash. It contains no resume, job input or generated prose. Reserve capacity before calling the provider, release database locks during the call, and clean up only the failed request's receipt. Bound receipts to100 per profile and7days; expired metadata may be purged. Instance tokens are known to clients and cannot serve as a server-only HMAC signing key, so receipts use random opaque IDs and stored authoritative metadata.

Explicit POST /jobs/{job_id}/tailoring/drafts saves {receipt_id,draft,review_acknowledged:true}. Provider/source fields come from the server receipt, never from the mutable active profile or client declarations. Saving creates a private reviewed draft and leaves the active profile unchanged. Saved content is user-reviewed and may differ from generated content. Private list/detail/deletion routes are bounded to50 saved tailoring drafts per job/owner. Deleting a transient source revision invalidates that generation's ability to save; a saved tailoring reference protects its source revision until that draft is deleted.

A separate POST /jobs/{job_id}/tailoring/drafts/{draft_id}/accept accepts {expected_revision,review_acknowledged:true}. It applies the exact saved resume text and derives skills onto the current profile, preserving its other identity, experience and preference fields, then creates an immutable revision and re-scores. It does not restore all of the source profile. A newer active revision produces409 with no automatic retry or token adoption. The UI must retain the reviewed text and explain the conflict. Saving, editing and activation remain distinct actions.

Implementation ownership: backend_review owns backend, migrations and backup compatibility; frontend_review owns the separate tailoring panel and web API/types; root owns integration review, browser acceptance and all expensive/full checks. The extension-consent local commit ed0479c is unpushed because its required full gate exited75 before executing; the next settled combined gate must cover both increments before any push. No paid provider, credentials, cloud or routing action is authorized by this contract.
