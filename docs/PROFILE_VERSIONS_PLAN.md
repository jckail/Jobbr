# Profile revisions and resume tailoring: source review

Reviewed against the current source after the verified discovery increment f57b31e. Immutable profile history is implemented and verified locally; tailoring and generation provenance remain pending. Keep the existing active Profile row and IDs so current scoring, application history and API clients remain compatible.

## Immutable profile history (implemented foundation)

Add owner-scoped, bounded immutable profile revisions with a saved timestamp, content fingerprint and every profile scoring field; the initial interface labels revisions by timestamp and ID. Explicit profile save creates a revision transactionally; identical content may reuse the current revision. Explicit activation restores the selected snapshot and re-scores jobs. Expected revision checks reject stale concurrent saves/activation with409. Backfill an initial revision from the existing profile without inventing an original creation date.

Revision list/detail/activation/deletion must use the stronger private draft access gate, because public demo profile reads do not justify exposing historical resumes. Define count/content limits and referenced-revision deletion behavior. Document that backups retain historical resume text. PDF previews must stay transient and create no revision until an explicit save.

## Generation and review (remaining work)

Add a separate tailoring schema/endpoint that receives an explicit revision ID and job ID. Reuse existing OpenAI/Claude dispatch and evidence validation. Return proposed resume text, evidence-backed changes, unresolved gaps and source provenance captured before generation: revision ID and job-input fingerprint.

Generation is transient. Saving reviewed text and explicitly accepting it as a new active profile revision are separate actions. Edited saved results are reviewed user content; do not imply the server certified every edited claim. Existing drafts retain unknown revision provenance. Current saved draft fingerprints are computed from mutable sources at save time; that is insufficient to identify earlier generation inputs.

## Migration and acceptance requirements

Before adding migration0004, freeze/register the current0003 schema in backup verification alongside0001/0002. Preserve existing profile IDs and old saved draft JSON. Verify SQLite and PostgreSQL upgrade plus restore of old and new backups.

The central acceptance scenario: generate from revisionA, activateB while generation runs, then save the result. The saved result must remain bound toA; saving must not activateA, overwriteB, or recompute provenance fromB. Also prove explicit restore/re-scoring, stale-save rejection, private access to history, bounded history/content, referenced revision deletion behavior, invented-evidence rejection and PDF preview creating no revision.

Sources: backend/jobbr/models.py, services.py, career.py, drafts.py, api.py; backend/migrations; scripts/backup.py; docs/RESUME.md and ROADMAP.md. History foundation passed mandatory local verification, including PostgreSQL concurrency and historical/current backups. The tailoring portion is a remaining implementation plan, not completed functionality or live provider acceptance. No credential, paid provider, cloud or routing action is authorized by this plan.
