# Manual production release

`.github/workflows/deploy-cloud-run.yml` prepares a reviewed manual release for the existing `jobbr` Cloud Run service in `portfolio-383615`, `us-central1`. Adding the workflow does not deploy, create resources, configure IAM, or change DNS. Root review and production configuration are prerequisites to dispatch. Its external GitHub/GCP path has not yet been executed or validated end to end.

## Release inputs and provenance

Dispatch the workflow from `main`, with the exact GHCR `sha256:` image digest, its full 40-character main source commit, and the successful main CI run ID. Other refs/repositories cannot reach the deployment job. Inputs enter Python through environment variables and are strictly validated before use; they are never interpolated into shell code.

The first job has no Google OIDC permission. It authenticates to GHCR with the scoped GitHub token, then uses [GitHub CLI attestation verification](https://cli.github.com/manual/gh_attestation_verify) to check the exact OCI image from `ghcr.io/jckail/jobbr`, this repository's `.github/workflows/ci.yml` signer identity on `refs/heads/main`, source and signer commit, and GitHub hosted execution. It also checks the GitHub Actions API for a completed successful push run from this repository/main, successful `image-publish` job, and the verified statement's matching run-attempt invocation, workflow metadata and subject digest. A historical failed or mismatched attempt fails closed. Provenance metadata is supplied by the trusted signing workflow; the certificate/signature checks establish that workflow identity. Review changes to CI's signing logic as release security changes.

CI currently tests and scans an image artifact before `image-publish` downloads and publishes it. The attestation identifies the publishing workflow execution and source, rather than asserting a new image build in that publishing job. The release workflow consumes this existing provenance contract.

## Production configuration

Configure these GitHub variables in the protected `production` environment. Empty, different-resource or `latest` references fail before Google authentication.

| Variable | Required value |
| --- | --- |
| `GCP_WIF_PROVIDER` | Reviewed `projects/NUMBER/locations/global/workloadIdentityPools/POOL/providers/PROVIDER` resource |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | `jobbr-deployer@portfolio-383615.iam.gserviceaccount.com` |
| `JOBBR_RUNTIME_SERVICE_ACCOUNT` | `jobbr-runtime@portfolio-383615.iam.gserviceaccount.com` |
| `JOBBR_ARTIFACT_REPOSITORY` | `jobbr` |
| `JOBBR_DATABASE_SECRET_REF` | `jobbr-database-url:N`, positive numeric version |
| `JOBBR_API_TOKEN_SECRET_REF` | `jobbr-instance-token:N`, positive numeric version |
| `JOBBR_AUTH_STORE_SECRET_REF` | `jobbr-auth-store-key:N`, positive numeric version |

Restrict the environment to main and configure required reviewers where supported. Configure [Google Workload Identity Federation](https://github.com/google-github-actions/auth) separately, bound to the exact numeric GitHub repository ID and owner ID, `ref=refs/heads/main`, the exact `workflow_ref` `jckail/Jobbr/.github/workflows/deploy-cloud-run.yml@refs/heads/main`, and subject `repo:jckail/Jobbr:environment:production`. Validate the actual issued claims and audience before enabling the provider; the environment name is represented in the subject. Do not broaden trust to all repositories, branches or workflows. The workflow never creates a provider or service-account key.

Grant the deploy account only the required existing-resource permissions: update the Jobbr Cloud Run service/revisions/traffic; impersonate the dedicated runtime account; upload/read images in the dedicated Artifact Registry repository; read the dedicated Cloud SQL instance, runtime account and secret-version metadata. Project-level SQL instance metadata reads may need a small custom role because this API is project scoped. Runtime permissions belong to `jobbr-runtime`: Cloud SQL Client and Secret Manager Secret Accessor for the three dedicated secrets. The deploy job does not read secret payloads. Do not grant Owner/Editor or Secret Accessor to the deploy account merely to make these checks work.

The existing service must explicitly declare `JOBBR_PRIVATE_INSTANCE=true`, `JOBBR_SEED_DEMO=false`, and `JOBBR_OPENAI_AUTH_ENABLED=false`, with one container and an HTTP `/healthz` startup probe on port 8000. Missing values, an OAuth-enabled service, or a different probe fail closed after Google authentication but before any service update. This workflow cannot convert an OAuth service into token mode. Other existing authentication settings are preserved.

All of the following must already exist: the service `jobbr`, runtime account, RUNNABLE PostgreSQL instance `jobbr-pg` with connection `portfolio-383615:us-central1:jobbr-pg`, standard Docker Artifact Registry repository `jobbr`, and the three enabled numeric secret versions. The database secret must contain the reviewed dedicated PostgreSQL connection string using the Cloud SQL Unix socket. The workflow does not initialize resources, rotate credentials or enable OAuth.

## Digest-preserving registry mirror

Cloud Run consumes `us-central1-docker.pkg.dev/portfolio-383615/jobbr/jobbr@sha256:...`. This avoids depending on GHCR package visibility or assuming private GHCR support. The workflow pulls the official Skopeo stable image before requesting short-lived Google credentials, pinned to manifest-index digest `sha256:249b92db7297e5c801e19172dbb3b56fde88094a49740a5ededac8c2958bf2c0`. Actions also use immutable commit pins. The Google CLI installation uses the supported version range declared in the workflow, so it is not a byte-for-byte toolchain lock.

[Skopeo copy](https://github.com/containers/skopeo/blob/main/docs/skopeo-copy.1.md) runs with `--all --preserve-digests`: unsupported transformations fail. It copies from the verified source digest, checks the returned destination digest, then fetches the destination's raw manifest and hashes its unchanged bytes against the verified SHA256. The [official inspect implementation](https://github.com/containers/skopeo/blob/main/cmd/skopeo/inspect.go) writes raw manifest bytes without output framing. The destination tag is only a copy target; deployment uses the digest. GHCR attestation referrers are not copied or claimed to exist in Artifact Registry: the chain is verified source provenance plus identical destination manifest digest.

Registry credentials are held in a mode-0600 temporary auth file removed when the mirror step exits. They are neither command-line passwords nor build arguments; subprocess output is captured and failures are sanitized. The tool container has a read-only root, dropped capabilities and no-new-privileges. GitHub runner cleanup handles credentials if the job is forcibly interrupted.

## Service update and failure behavior

The release preserves ingress, invoker IAM, domains and other applications. It updates the existing service's image, dedicated runtime identity, sole Cloud SQL integration, numeric secret references and reviewed resource limits. Private token mode is required both before the update and on the exact resulting revision: `JOBBR_PRIVATE_INSTANCE=true`, `JOBBR_SEED_DEMO=false`, `JOBBR_OPENAI_AUTH_ENABLED=false`. This workflow is only for the interim token-mode service; an owner OAuth service requires a separate reviewed release configuration.

The existing-service [update command](https://docs.cloud.google.com/sdk/gcloud/reference/run/services/update) creates a new revision without traffic; it does not use the service-creating deploy command. The revision suffix is `release-GITHUB_RUN_ID-GITHUB_RUN_ATTEMPT`, derived from validated numeric runner metadata. The returned revision must exactly match that run identity. The workflow then verifies the revision name, Ready=True condition, image digest, runtime service account, sole Cloud SQL integration, three numeric secret references, token-mode environment settings and HTTP health startup probe before directing traffic to that specific revision. Deployment health checks are explicitly enabled. This is a Cloud Run startup-probe check; no private API access, authenticated CRUD, signed-in application or database smoke check is claimed. Failure before promotion leaves existing traffic unchanged. A promotion error requires inspecting service status rather than assuming rollback. Releases are serialized and are never automatically cancelled midway.

To roll back, review and dispatch a prior verified successful main release digest and its successful CI run, with compatible pinned secret versions. Database migrations run during no-traffic revision startup against the same production database used by the serving revision. No-traffic staging is not database isolation. Review migration compatibility with the serving revision before dispatch, even when promotion may later fail. An older image is not necessarily compatible with the current schema. Establish compatibility before promoting a rollback. This workflow does not perform destructive database rollback or automatically delete prior revisions/images.

## Offline gate review

The workflow's Python blocks can be extracted and AST-compiled without authenticating or invoking subprocesses. For mocked behavior checks, the existing-resource block's `query` function is the boundary: supply service JSON containing one container, the three exact plain environment values, and `startupProbe.httpGet` with path `/healthz` and port `8000`. Reject missing/duplicate flags, OAuth `true`, private `false`, seeding `true`, a TCP probe, or a different path/port. Remaining fixtures provide SQL RUNNABLE/connection name, a standard Docker repository, and enabled numeric versions.

For the final block, mock `subprocess.run`: return the exact `jobbr-release-ID-ATTEMPT` name from the update; return full revision JSON from describe; record traffic updates. A successful fixture needs `metadata.name`, the exact `metadata.annotations["run.googleapis.com/cloudsql-instances"]`, `status.conditions` containing `{type: Ready, status: "True"}`, `spec.serviceAccountName`, and one container with the exact image, required probe and environment. Secret entries use `valueFrom.secretKeyRef.name/key`, without plain `value`. Independently change each field, return a different same-image revision name, or provide invalid runner IDs: every mismatch must prevent the traffic-update call. The automated regression tests below exercise these offline fixture cases. Their passing results do not validate the external cloud path or prove a deployed private API.


## Offline regression checks

Run `python3 scripts/test_cloud_run_release.py` without credentials. The seven test methods include subcases for unexpected OAuth/public/demo settings, missing or TCP startup probes, ambiguous environment variables, concurrent revision selection, readiness, image/identity/SQL mismatches, changed or plaintext secret references and invalid revision identifiers. All subprocesses are mocked. Hosted backend CI runs these guards before installing backend dependencies. Passing these checks proves fail-closed behavior for the fixtures; it does not validate Google IAM, an actual rollout, provider login or authenticated database smoke.
