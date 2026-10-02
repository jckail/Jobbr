# Verified checkpoint

Development worktree: `/home/jkail/jobbr-v2`, existing draft branch `claude/beautiful-sagan-mtnuvk`, PR https://github.com/jckail/Jobbr/pull/1. Original dirty main worktree remains intact. No legacy files deleted.

Implemented: OpenAI Agents SDK extraction and career API, single-owner ChatGPT OIDC backend and private access checks, Alembic migration/adoption, pinned SSRF-safe fetching, Chrome capture extension, lockfiles/audits, Docker/Compose and stronger CI. Superdesign command-center mockup version 3 is stored in `.superdesign/resume.json` and linked from DESIGN.md.

Checks: 115 backend tests passed with live disposable PostgreSQL 17; Ruff check/format and strict mypy passed. Web ESLint/TypeScript/Vite build passed; four extension tests passed. npm and pip audits found no known vulnerabilities. Docker build and read-only/dropped-capability smoke passed. Installed wheel migrations ran twice from `/tmp` in the container. Public HTTPS fetching succeeded with the pinned transport.

Local instance: Compose `jobbr-v2-app-1` healthy on http://localhost:8000/jobbr/, named persistent volume. Local UI is still v2 baseline pending the next implementation increment. After the user requested one tab per session, the browser tool reported prior pages absent and only blank tab 57 available. Root will reuse tab 57 for local checks; do not alter other agents' tabs.

Latest steering: user says resume all work; continue implementing the reviewed prototype direction and keep browser tabs bounded. Provider registration/live login and paid generation, PDF import, full frontend browser acceptance, extension browser acceptance, production GCP/Kubernetes deployment and legacy cleanup approval remain outstanding. See ROADMAP.md for full scope.

Agent Hub cannot save Jobbr checkpoint because no memory scope is configured. Shared Graphify lacks Jobbr code coverage; requested refresh is queued behind existing live processes. Direct live source is authoritative.
