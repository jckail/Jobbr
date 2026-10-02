# Jobbr overhaul: delivery requirements

Target: a private job-search workspace at https://jckail.com/jobbr, with an excellent Superdesign-backed web app, Chrome capture extension, explainable job matching, OpenAI Agents SDK assistance, Sign in with ChatGPT, reliable CI/CD and security, local Docker first and Kubernetes/GCP deployment later. iOS is explicitly a later platform.

## Delivered in this increment

- Recovered latest v2 branch into `/home/jkail/jobbr-v2`, preserving dirty main workspace.
- Superdesign command-center prototype and implemented web direction following the user’s resume-all instruction; desktop/mobile acceptance is in progress.
- OpenAI Agents SDK extraction and cover-letter/interview-preparation API; bounded requests, structured outputs, source evidence validation, tracing disabled. No live paid generation verified.
- Website identity-only Sign in with ChatGPT backend, private reads and CSRF-protected writes, single-owner subject restriction. Provider registration and real callback test still required.
- Alembic initial migration, validated adoption of existing v2 database and rejection of schema drift; fresh/repeated SQLite startup and PostgreSQL offline DDL checked.
- Manifest V3 extension with explicit tab capture, editable preview, destination restrictions, session-only token, and OIDC limitation messaging. Manual Chrome interaction verification pending.
- Locked backend dependencies, upgraded Vite/React plugin, local Compose, image smoke CI, immutable commit image tags and a private production Kubernetes manifest.

## Required remaining work

1. Finish browser acceptance of the implemented Superdesign across overview, searchable jobs, role detail, pipeline, profile and onboarding: desktop/mobile, keyboard, loading, empty, unauthorized and failure states.
2. Cookie authentication and consent-based career UI are implemented. Verify real provider login and paid generation, explicit private saved-draft persistence has passed hosted backend tests; complete browser acceptance; unknown spend is no longer shown as free.
3. Bounded PDF resume preview/import is implemented and tested, including malformed/scanned files and privacy. Immutable profile history and reviewed tailoring are now implemented with private server-captured provenance; complete real browser/provider acceptance and the next tested local upgrade.
4. Greenhouse/Lever discovery with checked source provenance and explicit saving is implemented; reminders are wired. Improve freshness/deduplication and richer search. Headless fetching needs a verified SSRF-safe browser strategy; extension capture already handles rendered text without backend browser access.
5. Add persistent user ownership and authenticated per-query authorization if expanding beyond the single-owner instance; shared encrypted transaction/session storage is implemented; PostgreSQL shared-session and startup-concurrency regressions passed hosted CI; verify production stable-key configuration before multiple workers/replicas. Current configured owner restriction must remain until this is verified.
6. Verify real ChatGPT client registration/callback and live SDK behavior using authorized server credentials; no ChatGPT-plan billing inferred from identity sign-in.
7. Complete real-Chrome acceptance of the implemented owner-approved, PKCE-bound extension authorization flow. Token capture remains available; registered website login, installation-path authorization and end-to-end popup verification remain pending.
8. Hosted PostgreSQL migration/CRUD and startup-contention tests pass. Verify production migrations/CRUD, backup/restore and upgrades before launch or scaling.
9. Finish CI/CD security gates (dependency/container/secret scans, least-privilege release credentials, image attestations, reviewable deployment), then provision approved GCP/Kubernetes target and verify https://jckail.com/jobbr end to end after local iteration.
10. Legacy removal pending exact-list approval in LEGACY_CLEANUP.md; credential rotation requires identifying owner-authorized credentials without exposing them.

Nothing here proves the full goal complete. Unit tests do not prove provider approval, visual quality, real browser extension behavior or production deployment.

## Additional verified evidence

165 backend tests now pass with a live, disposable PostgreSQL 17 service, including isolated-schema migrations, adoption, CRUD and persistence. The URL fetcher now pins validated public addresses on actual connections, preserves TLS hostname verification, checks each redirect and limits streamed response size; 23 dedicated tests and a real public HTTPS fetch passed. DNS now uses capped, killable subprocesses sharing the fetch deadline; focused resolver and fetch/discovery regressions passed. Full CI for this change remains pending. Both npm and pip dependency audits found no known vulnerabilities in the current locks.

Agent Hub currently has no configured Jobbr memory scope: `context` returned the repository-selection guidance and `checkpoint --cwd /home/jkail/jobbr-v2` rejected saving. This is a routing gap, not missing source. Verified project handoff remains in these local docs, with no remote memory upload. A shared Graphify refresh was requested but is waiting behind existing refresh processes; Jobbr code coverage was unavailable and source was verified directly.


## Earlier release evidence

Head b3a28a4 passed hosted CI run36966970247 for backend, web, extension, secrets and image smoke/security checks. PR1 remains draft; main publication and production release are unverified. CloudSQL jobbr-pg and dedicated runtime account, secrets and image repository exist; database bootstrap and Cloud Run service deployment await confirmation. No DNS/routing changes have occurred. The prepared manual workflow is under review, not executed. The latest handoff selected both OpenAI and Claude; implementation and offline review are authorized, while explicit confirmation remains required for credentials, paid calls and routing changes.


Both-provider implementation now uses explicit server selection and selected-key
gating, retains the existing OpenAI Agents path, and adds a bounded Claude Messages
path with no provider fallback. Focused89tests, backend strict types and web lint/types
passed. Browser disclosures pin provider/model/enabled configuration; stale selections
are rejected before generation. Full pre-push checks are running through the shared
guard after availability changed. No live provider generation, credentials or routing
action occurred; real provider and production acceptance requirements remain open.

## Discovery repeat-save increment (October 2)

Implemented exact-URL unchanged pasted-posting detection before extraction: matching stored text/full-source hash and absent or matching title/company hints return the existing job without changing application state or extraction records. Fetched HTML and explicit re-extraction retain their prior behavior. ATS snapshots retain the first safe posting per source ID inside the same 100-row window; unsafe duplicates cannot hide a later safe entry. Discovery searches now look up saved job URLs, preserving links across refreshed results, and explicitly explain snapshot freshness. Independent source review found no blockers; 53 focused backend cases, Ruff/format, strict mypy and web lint/types passed. Synthetic-response browser checks verified saved-role hydration, repeat search without a second save and visible lookup failure. Mandatory local full verification passed; publication and exact-SHA hosted CI verification follow.

Canonical ATS identities, database uniqueness/concurrent writes and upstream availability tracking remain follow-ups; a checked timestamp does not prove a posting remains available. Versioned resumes/profile tailoring, supported extension authentication/real Chrome acceptance and the explicitly gated provider/production work remain open.

Immutable profile-history foundation now includes private snapshots, explicit restore/re-scoring, monotonic stale-edit protection, non-recycled revision IDs, and historical/current backup compatibility. Mandatory local backend/web/extension verification passed; exact-SHA hosted CI follows publication. Tailoring and generation provenance tied to an explicitly selected revision remain open; see PROFILE_VERSIONS_PLAN.md.

## Latest verified implementation (October 2)

Immutable profile history atdb40e3f is pushed with green hosted CI and is running in the owned local Compose app with every prior product record preserved. The next reviewed increment implements revision-based resume tailoring, metadata-only generation receipts, separate save/activation, expected-version conflicts, frozen0004/additive0005 backup support, extension paid-provider consent/settings pins, and expired-session UI cleanup. Mandatory combined verification passed392backend cases including live PostgreSQL plus seven release and seven extension tests and all lint/types/build checks. Publication/exact-head hosted CI follows; paid provider and production acceptance remain unverified.

Shared Chrome extension tools are enabled, but install path authorization is being repaired by a separate maintenance agent. A source UI generation check was interrupted by its browser reconnect, so full tailoring browser and installed extension acceptance remain open. Resume root's synthetic fixture and real extension checks after the verified maintenance handoff. Existing saved cover-letter/interview drafts still have historical save-time fingerprints, not generation-revision provenance. Discovery canonical identity/concurrent duplicate prevention/freshness, supported direct OIDC extension authorization, live identity/provider setup, production bootstrap/routing, and owner-approved legacy cleanup/credential rotation remain tracked.


## Canonical capture and extension authorization source checkpoint

The isolated worktree `/home/jkail/jobbr-discovery-identity-20261002` integrates
remote d9d6947 with owner-approved direct extension capture and the additive
0007 canonical identity/lease increment. Known ATS aliases share one job; stale
provider results cannot overwrite a concurrently edited job. Ambiguous legacy
rows require review rather than merging. Capture and re-extraction pin checked
provider settings and release transactions before dispatch.

The first complete backend gate passed 527 cases with PostgreSQL and one
intentional skip, then failed two legacy mock signatures. Both corrected
regressions passed; the corrected full gate exited 75 before execution. Full
backend/web/extension/release checks are still required before publication.
Upstream availability/freshness tracking remains the next discovery increment.
Real Chrome, website registration, paid provider verification, the tested local
image upgrade and production acceptance remain open.


Explicit transient availability observations are now implemented and focused
backend checks pass. Complete the combined gate and rendered UI acceptance.
Persisted availability history, broader board completeness/pagination and
canonical saved-result hydration remain follow-ups; no automatic closing or
deleting is introduced.


Canonical saved-result hydration is now implemented: server-derived identities
preserve saved links across ATS aliases, and ambiguous saved matches require
review. Focused backend checks passed; combined verification and rendered
discovery acceptance remain required before publication.
