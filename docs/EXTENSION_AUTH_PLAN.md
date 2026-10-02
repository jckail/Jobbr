# Direct extension authorization

Implementation is in progress. Existing token-mode capture remains supported.
Real Chrome acceptance awaits the shared installation-path authorization repair;
website sign-in and paid provider calls have not been verified live.

## Connection protocol

1. The popup creates a random PKCE verifier and its S256 challenge locally.
   The verifier stays in trusted Chrome session storage, separated by destination.
2. The popup opens the configured website approval page with only the public
   Chrome extension ID and challenge in its fragment. No credential, verifier,
   resume or posting content belongs in the URL.
3. The website reads approval details without creating a pending database row.
   A signed-in owner reviews the destination, comparison code, limited scope and
   exact AI policy. An explicit CSRF-protected approval creates the pairing.
4. The popup explicitly finishes the connection by exchanging the extension ID,
   challenge and private verifier. Approval expires after five minutes; consumed
   pairing metadata prevents replay during that window.
5. The capture credential expires after fifteen minutes, allows at most five
   captures and permits one capture at a time. It has no refresh mechanism.

`JOBBR_EXTENSION_ALLOWED_IDS` contains reviewed Chrome IDs separated by commas.
Its empty default disables approval. An extension ID and browser Origin are
public metadata, not cryptographic proof of a client. Owner approval, the private
verifier and the scoped credential supply authority. This is internal Jobbr
delegation through the existing website session, not provider extension OAuth.

## Capture boundaries

Only the dedicated capture endpoint accepts this credential. It must not grant
profile, resume, notes, existing-job reads, exports or administration access.
Capture replies contain only the resulting job ID. Database records contain
credential hashes and bounded authorization metadata, never raw capabilities.

Capture reservations precede extraction, with an idempotency key and input digest.
Concurrent requests cannot bypass the budget or start duplicate extraction.
The selected provider, model and enabled state must match the approved policy;
each paid capture still requires explicit popup consent. No provider retry or
fallback is implied by connecting the extension.

New captures require the approving website session and authentication scope to
remain valid. Logout, expiry and revocation invalidate future reservations.
A capture already reserved may finish and save after those events; a provider
request already dispatched cannot be recalled. Credential expiry is also bounded
by the approving session's expiry. Tests still need to verify these boundaries.

## Verification before publication

Independent source review found no remaining authorization bypass or public
write-lock admission issue. It identified a missing backup check for the required
capture-throttle singleton; the fix and regression test now pass.
Existing migration and backup expectations now include revision 0006, and
historical backup verification includes revision 0005 and all existing tables.

Verified offline tests cover private approval and CSRF, unknown and disallowed IDs,
PKCE failures and replay, expiry and logout, scope isolation, policy changes,
idempotency, budget exhaustion and concurrent captures on SQLite and PostgreSQL.
The mandatory integration gate passed: 430 backend tests, one intentional skip
for a SQLite-only archive test under PostgreSQL, seven offline release tests,
seventeen extension tests, and required backend/web lint, types and build checks.
Real Chrome connection, popup capture and reload/forget behavior remain separate
acceptance checks. No real credentials, provider spending, cloud execution or
domain routing changes are authorized by this source implementation.
