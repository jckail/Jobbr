# Sign in with ChatGPT

Jobbr implements the **website identity-only** OpenID Connect flow described in the [official website guide](https://developers.openai.com/siwc/website). OpenAI's [registration page](https://developers.openai.com/siwc/request-client-id) says this integration is currently offered to selected commercial partners. A real website client ID and exact callback registration from OpenAI are required before this feature can work. An ordinary OpenAI API key, ChatGPT subscription, or illustrative client ID does not enable it. The separately documented dynamic open-source client flow has a different registration and plan-usage contract; this implementation does not substitute that flow.

## Required configuration

Environment variables are server-only. Keep secrets outside version control.

| Variable | Purpose |
| --- | --- |
| `JOBBR_OPENAI_AUTH_ENABLED=true` | Enable authentication and private API gating. |
| `JOBBR_OPENAI_CLIENT_ID` | Your registered website client ID. |
| `JOBBR_OPENAI_REDIRECT_URI` | Exact registered HTTPS callback, e.g. `https://your-host/jobbr/auth/openai/callback`; path must match `JOBBR_BASE_PATH`. |
| `JOBBR_OPENAI_TOKEN_AUTH_METHOD` | Registered method: `none` (public client, default) or `client_secret_basic` (confidential client). |
| `JOBBR_OPENAI_CLIENT_SECRET` | Required only for `client_secret_basic`; forbidden for `none`. |
| `JOBBR_OPENAI_ALLOWED_SUBJECT` | Exact verified OpenAI `sub` of the database owner. |

The owner subject must come from a verified identity through your registration/testing process. Do not use an email address as proof of ownership. There is deliberately no automatic first-user enrollment or fallback to accepting every OpenAI account. With authentication enabled but incomplete configuration, sign-in and protected API requests fail closed. Status includes a configuration reason without exposing credentials. Local browser testing also needs an HTTPS endpoint and an exact registered callback; insecure session cookies are not offered as a workaround.

**This database remains single-owner.** Jobs, resumes and pipelines have no user partition. Authentication admits only the configured owner subject and does not create multi-user isolation. Before admitting additional accounts, add persistent users and issuer/client/subject mappings, owner foreign keys, per-query authorization, and a verified data migration. Do not remove the subject restriction before that work is complete.

## Integration contract

Create `AuthService(AuthSettings(), base=settings.base)`, set `app.state.auth`, and mount `build_auth_router(service)` under that same base. `require_session(request)` enforces the owner session; `require_csrf(request)` additionally enforces an exact `Origin` and matching `X-CSRF-Token`. Apply session checks to private API reads and CSRF checks to every cookie-authorized write. The existing optional `X-Jobbr-Token` is a separate write credential and must not bypass enabled session authentication.

Routes (prepend the configured base):

- `GET /api/auth/session`: configuration readiness, authenticated state, minimal owner identity, CSRF token and sign-in URL. Returns `Cache-Control: no-store`.
- `GET /auth/openai`: begins authentication and redirects to OpenAI.
- `GET /auth/openai/callback`: consumes the bound, one-time transaction, redeems the code, validates identity, and redirects to the application.
- `POST /api/auth/logout`: requires session, exact same-origin `Origin`, and `X-CSRF-Token`; revokes the first-party session and clears its cookie.

Browser code sends cookies with same-origin requests, reads its CSRF token from the session endpoint, and includes that token only for writes. Do not store OAuth tokens, authorization codes, PKCE verifiers or secrets in localStorage, sessionStorage or browser JavaScript. The backend discards raw provider tokens after validation. Logout affects only Jobbr's session, not the user's ChatGPT session.

## Security and operational boundaries

The provider's endpoints and signing algorithms are obtained from the [documented production discovery URL](https://auth.openai.com/.well-known/openid-configuration). Discovery must identify `https://auth.openai.com`, and all fetched endpoints must stay on that HTTPS host. Requests do not follow redirects or environment proxies. Each response is capped at 128 KiB, each network operation has a five-second timeout, and each sign-in operation has a twelve-second overall budget.

A new sign-in has independent random state, S256 PKCE and nonce, bound to a random browser cookie. Transactions expire after ten minutes and are consumed before code exchange on success or failure. Temporary cookies are cleared on callback completion. ID tokens require a valid asymmetric JWKS signature, exact issuer, client audience, subject, expiration, issued-at and nonce, with five seconds of clock tolerance. Authorized-party claims are checked when present and required for multiple audiences. Metadata is cached for an hour; JWKS for five minutes, with an unfamiliar key triggering refresh at most once per five seconds. Neither unverified token claims nor email matching establish account ownership.

Session cookies are `__Host-` cookies with `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, and an eight-hour lifetime. Sessions rotate after successful login. The session and transaction stores are in server memory, expire records, and each cap at 1,024 entries. **Run exactly one application worker/instance for this implementation.** Restarting expires all sessions. Production scale-out requires a shared TTL store with atomic transaction consumption and session revocation; sticky routing alone does not provide that guarantee. Reverse proxies should suppress callback query strings from access logs, because they contain temporary authorization codes. Serve the app using HTTPS.

Tests use mocked discovery, token exchange and JWKS plus locally generated signing keys; they require no OpenAI credentials. This verifies the application flow, not partner approval or a live registration. Complete a real registered-client acceptance test before launch.

## Browser access controls

The web client reads only public configuration and session status before mounting private pages. When OpenAI authentication is enabled, saved jobs and profiles are requested only after an authenticated session is confirmed. In private token mode, the client validates the token against a protected read before displaying the workspace. A rejected session closes the private view and reloads access status. The Access/Account control exposes sign-in, current owner identity, logout, and configuration or connection failures; an unavailable provider is never replaced with a simulated signed-in state.

Legacy `localStorage` access tokens are deleted when credentials are read or written. Instance access tokens now live in `sessionStorage` for the current tab session; users can clear them through Access. OAuth tokens are never exposed or stored there. The first-party CSRF token is kept only in JavaScript memory, loaded from the authenticated session endpoint, and attached to cookie-authorized writes, including multipart resume previews and logout.

AI career drafting is a separate, explicit action. The user must confirm which saved candidate and role facts will be sent to OpenAI before requesting a letter or interview preparation. Both drafting actions stay disabled while a request is running. Responses show profile evidence, review notes, model and token usage; drafts must be checked before use and are never sent to an employer automatically. Connection or generation failures remain errors without substituted output.
