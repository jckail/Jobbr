# Private saved career drafts

AI generation remains transient. A generated letter or interview plan is written
to the database only when the owner explicitly saves it. No save request calls AI.
Drafts remain available after reload without another generation call.

The saved-draft API always requires the authenticated owner session or the
configured instance API token, including on an otherwise publicly readable demo.
Session writes also require the existing origin/CSRF checks. Open deployments
without either credential cannot save or read drafts. Every lookup scopes the
record to the requested job and the single current owner profile.

- `POST /api/jobs/{job_id}/career/drafts`: `{ "result": CareerResult }`; returns 201.
- `GET /api/jobs/{job_id}/career/drafts`: up to 50 complete records, newest first.
- `GET /api/jobs/{job_id}/career/drafts/{draft_id}`: one record, or 404.
- `DELETE /api/jobs/{job_id}/career/drafts/{draft_id}`: 204; explicit owner action.

All paths use the configured mount prefix. Records contain `id`, `job_id`,
`created_at`, `source_fingerprint`, and `result`. The result includes kind,
model, token usage, content, evidence quotations, review notes, and optional
`generated_at`. `created_at` is the server save date; `generated_at`, model, and
usage are submitted metadata and cannot certify where user-edited content came
from. A save does not validate quotations against the resume or verify factual
claims. `requires_review` always remains true. Review claims before using a draft.

`source_fingerprint` hashes the job/company/profile state at save time, not at
claimed generation time. It can detect subsequent changes without duplicating
the resume or posting. The record stores only submitted result content and
bounded evidence quotes; there is no separate resume or raw source snapshot.
Unknown fields are rejected. Serialized input is limited to 64 KiB, letters to
12,000 characters, interview questions to eight, and supporting lists/strings to
bounded lengths. There are at most 50 saved drafts per job/profile; saving a 51st
returns 409 until the owner deletes one. Deleting a job also deletes its drafts.

Migration `0002_saved_drafts` adds a table without rewriting existing records.
Prior versioned snapshots remain verifiable/restorable with the backup tool;
restoring copies the archive unchanged and startup upgrades only that copy.
Backups contain private draft content and should be protected like resumes.
