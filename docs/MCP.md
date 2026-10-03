# Authenticated Jobbr MCP

This resource server extends the v2 application on `main`. It uses the existing
SQLModel Company, Job, Extraction and Application tables and preserves canonical
job identities when filtering the shared repository queries. It changes neither
the schema, website login nor deployment configuration. It is implemented and locally
testable; it is **not deployed or connected to ChatGPT**.

## Tools and permissions

| Tool | Additional scope beyond `jobbr:read` | Behavior |
| --- | --- | --- |
| `search_companies` | none | Company name search, stable ID pagination |
| `search_roles` | none | Search title/company/team/skills; optional company ID |
| `get_role` | none | Skills, department, role context and up to ten extraction sources |
| `get_refresh_status` | none | Last observation, latest extraction result and seven-day staleness |
| `list_shortlist` | `jobbr:shortlist:read` | Saved pipeline, notes and next-step dates |
| `update_shortlist_notes` | `jobbr:shortlist:write` | Replace notes on an existing Saved application |

The write tool is absent unless `JOBBR_MCP_ENABLE_SHORTLIST_WRITE=true`. A single
conditional database update checks the Saved stage; it cannot reset an applied
role, create an application, send outreach, or submit anything. Notes are replaced,
including by an empty string. Reads never create a profile, re-extract a posting,
fetch a URL, or invoke a paid model. All tool definitions carry OAuth metadata and
read/write annotations; authorization is enforced independently of those hints.

Search pages default to 25 and cap at 50; use the returned `next_after_id`. Text and
lists are bounded. Role details omit raw postings, resumes, application notes and
provider error payloads. Shortlist notes require their separate read scope.
Imported recruiter review summaries also remain in the scoped shortlist notes,
including for older imports that duplicated the summary into ordinary role context.
Posting content is untrusted source data, not instructions to an agent.

`posted_at` is the parsed posting date and remains null when unknown.
`first_seen_at` is when Jobbr first discovered the role. `last_seen_at` is the last
stored observation. These dates are never substituted for one another. Extraction
success does not verify that the job is open. Freshness reports no live-posting
verification and unknown running-refresh status because the current data model
has no durable refresh queue. Shortlist means the existing UI's Saved stage,
including implicitly Saved jobs without an Application row; the notes writer
requires an existing row.

## Owner isolation

The existing v2 database is **single-owner**, as described in [AUTH.md](AUTH.md).
MCP admits exactly one configured `(issuer, client_id, subject)` identity. All
other subjects are rejected before tool dispatch or database queries. There is
no user ID parameter, email-based linking, automatic enrollment, or interpretation
of an OAuth client ID as a user. Stateless HTTP prevents server sessions from
carrying one caller's identity to another request. Every HTTP request is verified.

This is not multi-tenant storage. Do not add multiple allowed subjects or share a
database across owners without implementing the ownership migration and query
isolation described in AUTH.md. For this increment, deploy one database/resource
configuration per owner. The administrator must verify that the configured MCP
subject belongs to that database's owner; an external issuer's subject need not
equal the OpenAI website-login subject. Enabling MCP also does not privatize the
existing website; keep its existing private-instance authentication enabled before
using private data.

## OAuth resource-server contract

ChatGPT is the OAuth client. An existing, separately operated OAuth 2.1
authorization server handles user login, consent, PKCE authorization codes,
refresh tokens and client registration. Jobbr implements the protected resource,
not a new authorization server. No client or grant is registered by this code.

Configure that authorization server for:

- Authorization code with PKCE S256, exact registered callbacks and user consent.
- RFC 8414 or OIDC discovery with S256 advertised; prefer Client ID Metadata
  Documents (CIMD) where supported. Pre-registration also works. DCR is retained
  for older clients but deprecated in the July 2026 MCP specification.
- RFC 8707 `resource` in both authorization and token requests, bound to the
  Jobbr MCP canonical URL as the access token's exact audience.
- RFC 9068 asymmetric JWT access tokens: `typ=at+jwt`, a unique `kid`, `iss`,
  string `aud`, `sub`, `client_id`, `scope`, `iat`, and `exp`. Token lifetime must
  be at most one hour. Supported algorithms are RS256, PS256 and ES256.
- Only the exact requested, consented tool scopes. Never use client credentials
  to stand in for the human owner.

The verifier checks signature, issuer, exact audience, expiry/not-before,
issued-at, lifetime, approved client, owner subject and exact scope membership.
Missing claims, wrong token type, algorithm confusion, arbitrary bearer strings,
OpenAI identity tokens and downstream API tokens fail closed. It only fetches the
configured HTTPS JWKS endpoint, never a JWT-supplied URL, follows no redirects,
ignores environment proxies and sends no bearer token downstream. Key responses
are capped at 128 KiB; keys cache for five minutes; unknown-key refresh attempts
are throttled to once per five seconds. Requests have bounded timeouts. Credential
values and provider/database error payloads are not logged by these handlers.

The service exposes `/.well-known/oauth-protected-resource/jobbr/mcp` for the
default base. Missing/invalid credentials receive HTTP 401 plus discovery and
scope guidance. Missing base scope receives HTTP 403. Additional tool scopes
return an MCP error with `_meta["mcp/www_authenticate"]` so ChatGPT can request
step-up authorization. Minimal discovery advertises `jobbr:read`; individual tool
metadata declares shortlist permissions. Host/Origin checks stay enabled and the
HTTP body is limited to 32 KiB.

Bearer tokens remain replayable until expiry, as with normal OAuth bearer access.
This version does not introspect revocation: use short token lifetimes, stop access
at the edge for emergencies, and revoke grants at the authorization server.
Website logout does not revoke a separately granted MCP token. Deployers must
apply transport-level rate limits and redact Authorization headers and query
strings in proxy logs. Tokens in query strings, cookies and `X-Jobbr-Token` are
not accepted by the MCP endpoint.

## Configuration and local verification

Use the existing backend environment (`uv sync --locked --extra dev`, Python
3.12 as in CI). After migrating a **test or approved** database through the
existing Jobbr workflow, supply these server-only settings:

| Setting | Required value |
| --- | --- |
| `JOBBR_DATABASE_URL` | Existing v2 database connection |
| `JOBBR_BASE_PATH` | Existing base, `/jobbr` by default |
| `JOBBR_MCP_RESOURCE_URL` | Canonical HTTPS URL ending in `<base>/mcp` |
| `JOBBR_MCP_ISSUER` | Exact external authorization-server issuer |
| `JOBBR_MCP_JWKS_URL` | That issuer's verified HTTPS public-key endpoint |
| `JOBBR_MCP_CLIENT_ID` | Actual approved OAuth client identifier |
| `JOBBR_MCP_OWNER_SUBJECT` | Verified owner subject from that issuer |
| `JOBBR_MCP_ENABLE_SHORTLIST_WRITE` | `false` by default; opt-in notes updates |

No production values are supplied. The factory fails closed if configuration or
the existing schema is missing. It never seeds data or runs migrations.

```bash
cd backend
uv run --locked uvicorn jobbr.mcp_server:create_app --factory --host 127.0.0.1 --port 8001
uv run --locked pytest tests/test_mcp.py
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy --platform linux jobbr
```

The separate ASGI entry point preserves the current website process and image.
A later approved deployment can route only `/jobbr/mcp` and its protected-resource
metadata path to this process on the existing host; preserve the canonical Host
header and terminate TLS. Do not route legacy root APIs to it. Local tests use
synthetic SQLModel records, ephemeral signing keys and mocked JWKS; they do not
use any live Sheet, email, API keys, login sessions or production database.

## Check MCP routing and readiness

The default Docker/Compose command starts `jobbr.main:app`, the website. Its
`/healthz` probe checks that process. The website's SPA fallback can return HTML
with HTTP 200 for `GET /jobbr/mcp`; neither result establishes MCP availability.

For an approved MCP deployment, verify these steps in order:

1. Start the separate factory above and route both `/jobbr/mcp` and
   `/.well-known/oauth-protected-resource/jobbr/mcp` to it. Discovery is at the
   host root, outside `/jobbr`. The current `deploy/k8s.yaml` template routes only
   `/jobbr` to the website and does not configure this separate MCP service.
   Preserve the canonical Host header and existing website routes.
2. Fetch discovery from the intended HTTPS host. Require HTTP 200 with JSON,
   the exact configured `resource` URL, the expected issuer in
   `authorization_servers`, and `jobbr:read` in `scopes_supported`. Reject HTML,
   login pages, redirects to another service, and metadata for another resource.
3. Send an unauthenticated MCP `initialize` POST with
   `Accept: application/json, text/event-stream` and `Content-Type: application/json`.
   Require HTTP 401 and a `WWW-Authenticate` Bearer challenge pointing to that
   resource's metadata and advertising `jobbr:read`. HTTP 200 with a web page is
   a routing failure; a missing challenge is incomplete MCP readiness.
4. Using an already approved owner authorization, complete SDK initialization,
   `tools/list`, and a bounded read against the intended database. Verify wrong
   owner rejection and denial of shortlist notes without their additional scope.
5. Record the exact source/image, runtime, canonical URL and checked date. A real
   ChatGPT connection and scope escalation remain separate acceptance checks.

Discovery and the unauthenticated challenge establish routing/configuration
only. They do not establish live OAuth, authorized database access or ChatGPT
connectivity. Use synthetic identities only for local fixtures; do not register
a client or grant permissions as part of these routing checks.

## Sign in with ChatGPT is a separate flow

The current application already implements the website OIDC flow with state,
nonce, PKCE, one-time transactions, validated ID tokens and owner sessions; see
[AUTH.md](AUTH.md). As checked on **2026-10-02**, OpenAI documents it as a limited
commercial-partner trial requiring an issued website client ID and exact callback
registration. Leave it disabled until enrolled and configured.

Offering that sign-in inside a ChatGPT connector requires two independent OAuth
transactions: ChatGPT authorizes access with Jobbr's authorization server; that
server may use OpenAI to identify the user, then resume the outer consent/code
flow. Keep both transactions' state, PKCE, callbacks, codes and credentials
separate. Map inner identity by issuer + client ID + subject, never email alone.
The special connector-modal button also requires OpenAI activation. This increment
does not implement that authorization-server bridge or claim it is connected.

Neither OpenAI ID tokens nor consumer/Codex tokens are Jobbr MCP access tokens.
ChatGPT plan-funded inference is a different feature and is outside this change.

Official implementation references:

- [OpenAI MCP authentication](https://developers.openai.com/plugins/build/auth)
- [OpenAI website Sign in with ChatGPT](https://developers.openai.com/siwc/website)
- [Two-transaction connector sign-in](https://developers.openai.com/siwc/chatgpt-plugin)
- [MCP authorization specification, 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)
- [MCP client registration](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/client-registration)

Before a live connection: approve the provider/client registration and owner
binding, verify discovery/PKCE/resource-bound tokens against that provider,
approve deployment/routing, then complete a real ChatGPT connect/reconnect and
scope-escalation test. Do not use test fixtures as production credentials.
