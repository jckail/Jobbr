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
2. Cookie authentication and consent-based career UI are implemented. Verify real provider login and paid generation, then add useful draft persistence; unknown spend is no longer shown as free.
3. Bounded PDF resume preview/import is implemented and tested, including malformed/scanned files and privacy. Add versioned resume/profile handling and useful resume tailoring.
4. Greenhouse/Lever discovery with checked source provenance and explicit saving is implemented; reminders are wired. Improve freshness/deduplication and richer search. Headless fetching needs a verified SSRF-safe browser strategy; extension capture already handles rendered text without backend browser access.
5. Add persistent user ownership and authenticated per-query authorization if expanding beyond the single-owner instance; shared session storage before multiple workers/replicas. Current configured owner restriction must remain until this is verified.
6. Verify real ChatGPT client registration/callback and live SDK behavior using authorized server credentials; no ChatGPT-plan billing inferred from identity sign-in.
7. Test extension in real Chrome and design a supported extension authentication flow for OIDC; current token-only capture deliberately declines OIDC mode.
8. Verify live PostgreSQL migrations/CRUD, backup/restore and upgrades; improve concurrency/adoption for multi-pod startup when scaling.
9. Finish CI/CD security gates (dependency/container/secret scans, least-privilege release credentials, image attestations, reviewable deployment), then provision approved GCP/Kubernetes target and verify https://jckail.com/jobbr end to end after local iteration.
10. Legacy removal pending exact-list approval in LEGACY_CLEANUP.md; credential rotation requires identifying owner-authorized credentials without exposing them.

Nothing here proves the full goal complete. Unit tests do not prove provider approval, visual quality, real browser extension behavior or production deployment.

## Additional verified evidence

165 backend tests now pass with a live, disposable PostgreSQL 17 service, including isolated-schema migrations, adoption, CRUD and persistence. The URL fetcher now pins validated public addresses on actual connections, preserves TLS hostname verification, checks each redirect and limits streamed response size; 23 dedicated tests and a real public HTTPS fetch passed. Blocking system DNS remains a documented timeout limit. Both npm and pip dependency audits found no known vulnerabilities in the current locks.

Agent Hub currently has no configured Jobbr memory scope: `context` returned the repository-selection guidance and `checkpoint --cwd /home/jkail/jobbr-v2` rejected saving. This is a routing gap, not missing source. Verified project handoff remains in these local docs, with no remote memory upload. A shared Graphify refresh was requested but is waiting behind existing refresh processes; Jobbr code coverage was unavailable and source was verified directly.
