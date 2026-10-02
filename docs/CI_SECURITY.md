# CI security gates

The workflow keeps backend/Postgres, web and extension checks, dependency audits,
container smoke tests and main-only GHCR publication. It adds no deployment. Draft
branch pushes and pull requests still run checks. A shared concurrency key cancels
older overlapping branch/PR runs for the same source repository and branch; fork
repositories have separate keys. Sequential events can still cause two runs.

All directly used actions are pinned to immutable commit SHAs, with their reviewed
release versions in comments. Checkouts do not persist credentials. Read-only
`contents` access is the workflow default; only main's `image-publish` job receives
`packages: write`, `id-token: write` and `attestations: write`. PR and draft jobs
cannot publish or request signing identities. Job timeouts bound runaway work.

## Secret scanning

Gitleaks CLI v8.30.1 runs from a digest-pinned official container. The scanner gets
only a read-only source mount, dropped capabilities, no new privileges and no
network. Docker pulls its pinned image before starting that isolated container.
Output is redacted; no secret report artifact is uploaded.

The scan covers commits introduced by a push, or PR base-to-head commits. New branches
and missing pre-force-push commits use the merge base with main, with a last-commit
fallback when the base equals the head. GitHub event SHAs are validated before use.
This intentionally blocks newly introduced secrets without treating known legacy
history as a newly introduced change. It is not an all-history audit and does not
revoke old credentials. Historical rotation remains owner work described in
[LEGACY_CLEANUP.md](LEGACY_CLEANUP.md). No blanket baseline or ignore file is added.

## Image gate and publication

Trivy v0.70.0 scans the built runtime image for OS and language-package vulnerabilities.
The pinned Trivy action also pins its setup and cache actions. Fixable HIGH and
CRITICAL vulnerabilities fail the image job; scanner errors and unavailable databases
also fail. Unfixed findings, lower severities and configuration/secret image scans
are outside this gate. The live vulnerability database is intentionally refreshed,
so a previously passing pinned image can later fail. Resolve failures with patched
packages or updated pinned base images, then rebuild and rescan.

Main's image-test job exports the exact scanned and smoke-tested image as an immutable
run artifact retained for one day. Publication loads that artifact instead of doing
a second build, pushes a commit-SHA tag and attests the returned registry digest using
GitHub OIDC. Registry/signing credentials never enter the build/test jobs. Signing and GitHub CLI digest verification
happen after push, so an attestation or verification failure fails CI but does not
undo the pushed image. Consumers should require a verified attestation rather than trusting tags.
The attestation executes in `image-publish` and identifies this CI workflow/run as
the producer. Its subject is the exact image created by `image-test` in the same run;
it does not record the original build step's detailed commands, prove reproducibility,
or provide a separate builder-level SBOM attestation. Attestations establish workflow
provenance, not an absence of vulnerabilities.

To verify a published digest with GitHub CLI:

```sh
gh attestation verify oci://ghcr.io/jckail/jobbr@sha256:IMAGE_DIGEST -R jckail/Jobbr
```

Attestation availability depends on repository visibility and GitHub plan. The public
repository is supported by current plans. Moving to a private repository requires
checking GitHub's documented plan requirements. Branch protection must require the
security jobs to enforce merge blocking; workflow changes do not configure repository
branch protection.

## Verification limits

Local actionlint v1.7.12 validates workflow syntax. The commit-range script was exercised
with push, PR, initial-branch and missing-before events. A redacted Gitleaks scan of the
full `origin/main..HEAD` draft diff (1.33 MB) found no leaks. A real local Trivy scan of `jobbr:local` exercised
the new gate and found a fixable OS HIGH, demonstrating failure propagation; it did
not establish a clean image. The parent refreshed the base and added a bounded upgrade to the official Debian
security fix `libpcre2-8-0=10.46-1~deb13u3` for CVE-2026-103111; the rebuilt image
passed a fresh Trivy scan with zero findings in the configured fixable HIGH/CRITICAL
OS and Python scope. A redacted current-directory scan found three unchanged legacy
credentials in `api/learning/special.py:16`, `api/auth/user.py:19`, and
`api/auth/user.py:195`; all three finding lines were verified to exist in `origin/main`.
The directory scan capped individual files at 2 MB, excluding large generated caches.
These findings require owner-led rotation; they are not evidence of a new draft leak.
Hosted Actions artifact transfer, registry push, signing, plan permissions and consumer
verification require an actual main CI run; they have not been claimed as locally
verified. No registry publication or signing was performed during this edit.

Primary references: [Gitleaks CLI](https://github.com/gitleaks/gitleaks),
[Trivy action](https://github.com/aquasecurity/trivy-action),
[GitHub attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations),
and [immutable workflow artifacts](https://github.com/actions/upload-artifact).
