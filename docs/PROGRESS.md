# Verified checkpoint

Development worktree: `/home/jkail/jobbr-v2`, draft branch `claude/beautiful-sagan-mtnuvk`, PR https://github.com/jckail/Jobbr/pull/1. Original dirty main worktree remains intact. No legacy files deleted.

Implemented foundation: OpenAI Agents SDK extraction/career API, single-owner ChatGPT OIDC and private access checks, Alembic migration/adoption, pinned SSRF-safe fetching, Chrome capture extension, lockfiles/audits, Docker/Compose and CI. Foundation commit 47c75d7 passed hosted CI.

Current increment: reviewed Superdesign command center and responsive shell, gated quick search and session UI, consent-based career draft review/export, UTC reminders, bounded memory-only PDF preview with explicit acceptance/save, real Greenhouse/Lever board discovery with provenance and explicit saving, consistent verified SQLite backup/restore, and stronger security CI. Corrected USD-only salary median and extension company confirmation. Runtime Python base refreshed and Debian PCRE2 security fix pinned after the image scan detected a fixable HIGH.

Checks: 175 backend tests passed with live disposable PostgreSQL 17; one final additional backup race case brought its focused suite to 10 passing tests. Ruff check/format (including backup script) and strict mypy passed. Web ESLint/TypeScript/Vite build and four extension tests passed. Locked export matched. Docker non-root/read-only/dropped-capability smoke passed, including real PDF preview, unchanged saved profile, live 20-posting Greenhouse snapshot, and installed backup/restore/verify. Trivy image scan passed with zero fixable HIGH/CRITICAL OS/Python findings. Actionlint and CI commit-range fixtures passed. Full draft commit-range secret scan found no introduced secrets; three unchanged legacy credential findings need owner-led rotation.

Browser acceptance: root owns only tab 58 in isolated context `jobbr-root`; tab 57 belongs to another project and was untouched. Desktop 1440 and actual mobile 502 widths showed no horizontal overflow. Quick search navigated to a role and closed its dialog. No console errors in the checked public flows. Browser PDF upload extracted synthetic text; acceptance changed only the form until Save. Private gate requested only config/session before authorization, rejected wrong token, unlocked correct token with session-only storage, and closed quick search/reblocked access on expiry. Live discovery UI returned 20 current openings. Real ChatGPT login, paid generation and actual Chrome extension popup remain unverified.

Local instance: Compose `jobbr-v2-app-1` at http://localhost:8000/jobbr/ with persistent named volume. Disposable smoke/private QA containers were removed; PostgreSQL test service remains available. All browser work reuses root’s single tab.

Remaining: provider registration/live login and authorized generation, extension Chrome/OIDC verification, richer discovery/profile versioning/draft persistence, production GCP/Kubernetes deployment, and exact-list legacy cleanup approval. See ROADMAP.md. Full goal remains active and incomplete.

Agent Hub has no Jobbr memory scope; shared Graphify lacks Jobbr coverage and refresh remains queued behind pre-existing updates. No duplicate refresh was launched. Live source and these curated local docs remain authoritative; no private material uploaded.
