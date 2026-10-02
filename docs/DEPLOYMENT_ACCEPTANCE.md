# Production deployment acceptance

The target is `https://jckail.com/jobbr`. Local Compose verification and draft CI
do not establish a production deployment. `deploy/k8s.yaml` is a starting template;
the repository has no GCP provisioning or cluster deployment workflow. No project,
cluster, registry publication, production authentication or DNS ownership is
established by this document.

## Required launch evidence

Record the actual GCP project, cluster/location, Kubernetes context, ingress
controller/class, DNS owner and TLS mechanism before changing resources. Read the
existing `jckail.com` routing first: adding Jobbr must preserve other routes.
Confirm the selected project's billing, relevant APIs and deployment identity's
permissions without creating a replacement project merely because the CLI has no
default project. Use explicit project/context arguments throughout deployment.

Release from the exact reviewed commit. The current workflow publishes only a
successful `main` push; a successful draft/PR run does not exercise publication.
Require successful publication and attestation verification in that main run, then
independently verify the resulting image digest as described in
[CI_SECURITY.md](CI_SECURITY.md). Replace
`ghcr.io/jckail/jobbr:SET_VERIFIED_COMMIT_SHA` with the verified immutable
`ghcr.io/jckail/jobbr@sha256:…` reference in a reviewed deployment manifest.
Confirm the cluster can pull that image; private registry access requires a
separately provisioned pull credential. Never deploy the unresolved template tag.

Provision the namespace's `jobbr` Secret through an approved secret mechanism,
without committing or logging values. The template intentionally contains no
Secret. It requires private access and disables demo seeding. Select and verify
one of these modes:

- ChatGPT identity: real registered website client, exact HTTPS callback
  `https://jckail.com/jobbr/auth/openai/callback`, enabled authentication,
  registered token authentication method, and verified owner subject. Include
  the client secret only when the registration requires it. Complete the live
  sign-in and rejection cases in [AUTH.md](AUTH.md) before launch.
- Instance token: provision a strong `JOBBR_API_TOKEN`; verify unauthenticated
  reads/writes are denied and the correct token unlocks the workspace. This mode
  does not complete the separate Sign in with ChatGPT requirement.

An OpenAI API key enables paid AI separately from identity. Enable it only for
authorized generation, and verify the explicit input confirmation and error
behavior described in [AI.md](AI.md). Do not expose any provider credential to
the web bundle or extension.

Keep one replica and one Uvicorn worker. The template's `Recreate` strategy avoids
overlapping SQLite writers during rollout and causes a brief outage. PostgreSQL
alone does not permit OIDC scale-out: sessions and login transactions are currently
in process memory. Restarts invalidate sessions. Confirm the PVC's actual storage
class, persistence/reclaim policy, volume permissions for UID/fsGroup 10001 and
restore procedure. Take and verify a backup before replacing an existing database;
see [BACKUP.md](BACKUP.md). Startup performs migrations and rejects incompatible
schemas; do not mount a legacy database as a shortcut.

## Resolve ingress before applying the template

Choose a controller explicitly. The checked-in Ingress has no class and assumes
an installed cert-manager `letsencrypt` ClusterIssuer; that assumption is not
evidence either component exists. For a native GKE controller, review its Service
backend/NEG requirements and TLS mechanism and adapt the template accordingly.
The current Service is ClusterIP with no NEG or backend health-check configuration.
Do not mix cert-manager annotations with an unrelated TLS mechanism by assumption.

The application serves `/jobbr` itself, so preserve the prefix and avoid rewrites.
Pod probes use `/healthz` directly on port 8000. Verify the selected load balancer's
backend health check also reaches the appropriate health endpoint: the app's `/`
returns a redirect, and `/healthz` is outside the public Ingress prefix. A healthy
pod probe does not prove a healthy external backend. Confirm startup/migration
time fits the probe settings; add a startup probe when actual timing requires it.

Configure HTTPS, callback-query suppression in proxy access logs, and the
appropriate transport/security headers at the edge. Confirm certificate issuance
and renewal and that the existing site's certificate/routing remains intact.

## Reviewed rollout and acceptance

1. Save the final rendered manifest with the selected context, verified image
   digest, controller-specific configuration and Secret references; retain no
   credential values in the review artifact. Inspect the existing namespace,
   workloads, PVCs, Service, Ingress and related certificate/controller resources.
2. Validate the rendered manifest against the selected cluster with server-side
   dry-run, then inspect `kubectl diff` for that explicit context. Provision only
   the reviewed resources and apply the reviewed manifest. Record the rollout
   revision, image digest and deployment time.
3. Check rollout status, pod events/logs, bound PVC, readiness, Service endpoints,
   ingress backend health, external address and certificate. Do not treat
   `/healthz` alone as acceptance of auth, database correctness or external routing.
4. From the HTTPS target, verify UI/assets and direct navigation to a saved job;
   confirm `/jobbr/api/config` and session status work before login while private
   data remains denied. Use a synthetic record to test authorized profile/job/
   pipeline writes, refresh persistence and restart persistence. Clean up only
   acceptance records created for this check.
5. For OIDC, exercise successful owner login, a rejected non-owner, callback
   mismatch/replay rejection, CSRF rejection, logout and re-login after restart.
   Real provider registration is required; mocked tests cannot satisfy this gate.
6. If authorized, make one bounded paid AI request with synthetic candidate/job
   facts, confirm input disclosure and output evidence, and record actual usage.
   Verify unavailable AI remains an explicit error rather than substituted text.
7. Verify backup/export and restore to a separate database using the current image
   before calling launch complete. The Chrome extension currently declines OIDC
   instances; document that limit rather than accepting token mode as proof of
   OIDC extension support. See [EXTENSION.md](EXTENSION.md).

Keep the prior verified digest and backup reference available. A prior-image
rollback is safe only if its schema is compatible with the current database.
Otherwise restore into a separate database using the documented procedure and
review the switch; rolling back a Deployment does not roll back its PVC contents.
Record each acceptance result and any remaining launch blockers. A deployed pod,
green draft CI or reachable public shell is insufficient to mark the full goal
complete.
