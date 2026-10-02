# Chrome posting capture

`extension/` contains the Manifest V3 Jobbr extension. Capture reads the selected tab only after a click and creates an editable preview. Save sends the reviewed posting to the selected Jobbr destination. There are no background workers, automatic captures, polling, refresh credentials, remote scripts or analytics.

## Install and destinations

1. Use Chrome 109 or newer. In `chrome://extensions`, enable Developer mode and Load unpacked, selecting this repository's `extension/` directory.
2. Pin Jobbr and select Local (`http://localhost:8000/jobbr`) or Production (`https://jckail.com/jobbr`). Destinations are fixed; an arbitrary server URL cannot be supplied.
3. For a workspace using browser sign-in, connect using the steps below before capturing a posting. For token mode, enter the instance token under API token. Open local mode needs no token.
4. On the posting tab, open the popup and choose Capture current tab. Edit the URL and text and remove personal information. Save checks the latest extraction settings and requires confirmation of the provider, model, posting-text transfer and possible API charges when AI is enabled. Canceling sends no posting.

There is no build step. Reload the extension after source changes. Reloading, updating or restarting the browser clears its session credentials and pairing verifier. The legacy `mini_extension/` is preserved and is not used here.

## Direct private-workspace connection

The backend must have working website OIDC and the installed extension ID explicitly enabled in its reviewed non-secret `JOBBR_EXTENSION_ALLOWED_IDS` configuration. The value is a comma-separated list of reviewed 32-character Chrome extension IDs (letters a–p). The default allowlist is empty; a malformed list disables approval. Adding source alone does not enable production connections. Review the ID shown in the popup and `chrome://extensions`; an unpacked extension can have a different ID after moving its directory or loading it in another environment. No provider registration, production configuration or credential change is performed by loading this extension.

1. Expand Connect a private workspace and click Connect to Jobbr. The popup creates a local random verifier and S256 challenge and opens the selected fixed Jobbr approval page. This step sends no posting and makes no public pairing API request.
2. Sign in to Jobbr through the existing website flow. Check the destination, extension ID, capture permissions and eight-character comparison code against the popup. Explicitly approve. Website approval requires its HttpOnly owner session, exact website Origin and CSRF token.
3. Reopen the extension popup and click Finish connection. There is no automatic polling. A single exchange sends the verifier in the request body, never in a URL. The owner-approved pairing is valid for five minutes after approval; local pending details expire after ten minutes from Connect. If either window expires, start a fresh connection.
4. Return to the posting tab and capture/review it. Save sends directly to `/jobbr/api/extension/captures`, using the short-lived capture credential, exact AI settings pins and a fresh idempotency key. OIDC mode never falls back to the instance API token.

The credential grants `jobs:capture` for at most fifteen minutes, up to five captures and one active capture at a time. It cannot read the profile, resume, notes, existing job details or other private workspace data. The save receipt contains only a job ID. Open Jobbr normally to review the saved job; its website session stays separate. Signing out of the approving website session, expiry or owner revocation prevents new captures. Revocation cannot undo a request already authorized and running.

This is Jobbr capture authorization based on the website's OIDC owner identity. It is not an OpenAI-issued extension OAuth token and does not reuse or export the website session. The existing registered website client/callback is still required; no extension-specific provider callback or `chrome.identity` permission is introduced. Extension IDs and Origin checks restrict the reviewed browser client but are not cryptographic proof against a client outside the browser. Authority comes from explicit owner approval, the verifier-protected exchange and possession of the scoped credential.

## Disconnect and uncertainty

Disconnect / forget pairing removes the selected destination's local pairing and capture credential, then attempts to revoke that credential on the server. If revocation cannot be confirmed, revoke it in Jobbr or wait for expiry. Forgetting an unfinished local pairing does not cancel an approval already made in Jobbr. The website can revoke that access; an unexchanged approval expires after five minutes.

Each Finish or Save action makes one request sequence, with no automatic retry. If the popup closes, a response is invalid, or a connection times out, the operation may have completed. Check Jobbr before saving again. A repeated manual Save creates a new request identity and is not a recovery retry; it may perform extraction again. Server idempotency protects replay of the same identity, not a deliberate new Save. If exchange completed but its credential response was lost, revoke the grant in Jobbr and connect again. No refresh credential or website cookie is used to recover it.

Stale AI settings, expired approval, revocation, capture limits and overlapping captures fail visibly. Changing provider/model/enabled settings requires a new Save and disclosure review. Clearing posting text creates a URL-only payload; the server may fetch that page and send its posting text to the selected AI provider after confirmation. Your resume is excluded from extraction, and no dollar cost estimate is promised.

## Permissions and privacy

- `activeTab` and `scripting` read the current top-level tab following Capture. There are no persistent content scripts or broad posting-site permissions. The injected function receives only the text limit; no credential, pairing verifier or API token is passed into page JavaScript.
- `storage` persists only the destination selection in local storage. Instance tokens, pairing verifier/challenge and scoped credentials are separated by destination in trusted `chrome.storage.session`. They are never written to local/sync storage, page storage, URLs or logs. Storage initialization failures block connection and saving.
- The manifest declares `http://localhost:8000/jobbr/api/*` and `https://jckail.com/jobbr/api/*`, with a regression test guarding those declarations. Chrome [ignores the path component for host permissions](https://developer.chrome.com/docs/extensions/develop/concepts/match-patterns), so this is not browser-enforced isolation from other paths on those hosts. Fixed destinations and endpoint allowlists restrict actual requests, and CSP restricts the connection origins. All API calls omit browser cookies and reject redirects. Captures use bearer authorization only on their dedicated endpoint. Configuration reads include neither posting text nor credentials.
- Opening the reviewed approval tab requires no additional `tabs` permission; [Chrome documents tab creation without it](https://developer.chrome.com/docs/extensions/reference/api/tabs). No `cookies`, `identity` or `<all_urls>` permission is added.
- Captured previews remain only in popup memory and disappear when it closes. Connect before capture so opening the approval tab does not discard an unsaved preview. Capture reads rendered `document.body.innerText`, capped at 60,000 characters, plus the page URL. It does not deliberately read input values, cookies, network traffic, HTML source or iframe contents.
- URL fragments are removed, while query parameters remain visible for review. Remove sensitive query parameters and unrelated page text before saving. No screenshot or attachments are captured.

## Verification and release limits

Root owns verification. Focused source checks can use:

```sh
node --check extension/core.mjs
node --check extension/popup.mjs
node --test extension/*.test.mjs
```

The tests use synthetic credentials and mocked requests. They cover canonical destinations and approval routes, local S256 pairing/comparison codes, destination-separated expiry, single Finish with no polling, exact capture scope, secret-free errors, explicit paid consent, disabled/enabled AI pins, idempotency headers, cookie omission, redirect rejection, disconnect and unknown outcomes. They do not establish a working Chrome or provider connection.

Real Chrome verification remains required before declaring this path ready: load the installed ID, review and enable that ID through an authorized configuration change, check the actual extension Origin/CORS behavior, complete website approval, reopen and Finish, save a synthetic posting, and verify logout/revocation/expiry/limits and destination separation. Registered website OIDC and production routing must already be available. This source change performs none of those live operations and does not establish production readiness.

Chrome internal pages, the Chrome Web Store and other restricted tabs cannot be captured. Navigation text, lazy-loaded content, closed shadow roots and framed postings may produce incomplete previews. Review the text or paste the posting in Jobbr instead.
