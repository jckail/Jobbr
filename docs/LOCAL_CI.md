# Local release verification

Jobbr's automatic GitHub-hosted CI is disabled. Pushes and pull requests do not
run the archived CI workflow or publish an image. Its previous gate definitions
are preserved in [ci/hosted-ci.reference.yml](ci/hosted-ci.reference.yml), outside
GitHub's workflow directory. This is a change in execution location, not permission
to skip release checks. The separate manual Cloud Run release workflow is unchanged
and must not be dispatched for a new local release without approved provenance.

## One verification owner

Before an install, build or broad test, coordinate with the implementation owner
and inspect active checks across sibling worktrees. On GamingRig WSL, run each
expensive check through `/home/jkail/.local/bin/agent-heavy-check -- <command>`.
Run in the foreground; a busy-lock timeout is a blocker, not permission to bypass
the wrapper. Windows checks must coordinate with that same owner. Preserve active
worktrees, servers and databases.

Record the exact source commit, any uncommitted diff, tool versions, commands,
exit codes and local log paths. Freeze the source while the gate runs. A log from
a different commit or mutable source mount does not qualify a changed candidate.

## Required gates

Use Python 3.12, Node 22.12+ and locked dependencies. Run these gates on the
candidate before pushing application changes or merging a release:

1. Scan introduced commits with the pinned, redacting Gitleaks container from the
   archived workflow. Keep the source mount read-only and networking disabled.
2. Run `uv sync --project backend --locked --extra dev`; export locked production
   requirements and compare with `backend/requirements.lock`. Audit them with
   `pip-audit==2.10.1 --no-deps --disable-pip`.
3. Run backend Ruff, formatting, mypy and the full pytest suite, plus
   `python scripts/test_cloud_run_release.py`. Set `JOBBR_TEST_POSTGRES_URL` to an
   owner-created disposable database named `jobbr_test`; omitted PostgreSQL tests
   are incomplete verification. Never substitute a production database.
4. From `web`, run `npm ci`, `npm run check` and
   `npm audit --audit-level=high`. Run `node --test extension/*.test.mjs` from the
   repository root. For a disposable Linux copy of Windows source, exclude
   `node_modules` and install inside the destination. Diagnose executable or mount
   permission failures; do not weaken lint or treat a failed web gate as passing.
5. Validate the intended Compose configuration. Build the candidate image once,
   then run Trivy 0.70.0 for fixable HIGH/CRITICAL OS and library vulnerabilities.
   Scanner errors fail the gate. Retain the immutable tested image identity.
6. Run `scripts/smoke.py` only against an owner-created disposable instance using
   that image. It writes a synthetic job. Record source-to-image-to-container
   identity and cleanup; health alone is insufficient.

For MCP/proxy changes, additionally verify actual SDK negotiation, signed-token
negative cases, owner/scope boundaries and a repeat-safe reviewed-only import.
Check auth denial, CSRF, pipeline reload and logout in the authorized browser.
Synthetic identities and fixtures do not prove real OAuth, LinkedIn access or
provider execution. Keep real registrations, grants, paid calls and production
activation behind their existing action-time approvals.

## Publication and merge

Attach exact-source local verification evidence to the PR. Do not bypass required
branch protection if it still expects retired hosted checks; the repository owner
must reconcile its policy with local verification before merge. Do not create a
self-hosted runner registration, credential or access grant as a shortcut.

There is no automatic GHCR publication for new commits. Historical hosted
attestations still apply only to their original image/source/run. A local build
does not satisfy the manual deployment workflow's historical successful-main-CI
requirement. New image publication/provenance and production release need a
separately reviewed local release path; retain rollback and backup requirements.
