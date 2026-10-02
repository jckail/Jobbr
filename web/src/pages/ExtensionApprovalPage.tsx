import { useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage } from "../api";
import type { AuthSession, Config, ExtensionGrant } from "../types";
import { useAsync } from "../ui";
import { parseDate } from "../util";

export default function ExtensionApprovalPage({ requestPath, config, session }: { requestPath?: string; config: Config; session?: AuthSession }) {
  const owner = config.auth_enabled && !!session?.authenticated;
  const parts = requestPath?.split("/");
  const extensionId = parts?.[0];
  const requestId = parts?.[1];
  const validId = parts?.length === 2 && /^[a-p]{32}$/.test(extensionId ?? "") && /^[A-Za-z0-9_-]{43}$/.test(requestId ?? "");
  const details = useAsync(() => owner && validId ? api.extensionPairing(extensionId!, requestId!) : Promise.resolve(null), [owner, extensionId, requestId, validId]);
  const grants = useAsync(() => owner ? api.extensionGrants() : Promise.resolve([]), [owner]);
  const [reviewed, setReviewed] = useState(false);
  const [approved, setApproved] = useState(false);
  const [approvalExpiresAt, setApprovalExpiresAt] = useState<string | null>(null);
  const [freshReview, setFreshReview] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [now, setNow] = useState(Date.now());
  const running = useRef(false);
  const mounted = useRef(true);
  const policy = details.data;
  const reviewKey = JSON.stringify(policy ? [policy.request_id, policy.challenge, policy.extension_id, policy.destination, policy.comparison_code, policy.expires_at, policy.status, policy.scope, policy.capture_limit, policy.token_ttl_seconds, policy.ai_provider, policy.ai_model, policy.llm_enabled] : null);
  useEffect(() => { setReviewed(false); }, [reviewKey]);
  useEffect(() => {
    mounted.current = true;
    const timer = window.setInterval(() => setNow(Date.now()), 10_000);
    return () => { mounted.current = false; window.clearInterval(timer); };
  }, []);
  const exchangeDeadline = approvalExpiresAt ?? policy?.expires_at;
  const expires = exchangeDeadline ? parseDate(exchangeDeadline).getTime() : NaN;
  const expired = (approved || policy?.status === "approved") && (!Number.isFinite(expires) || expires <= now);
  const supportedPolicy = policy?.scope === "jobs:capture" && policy.capture_limit === 5 && policy.token_ttl_seconds === 900 && policy.request_id === requestId && policy.challenge === requestId && policy.extension_id === extensionId;
  const visibleGrants = grants.data?.filter(grant => parseDate(grant.expires_at).getTime() > now) ?? [];

  const refreshDetails = () => {
    setReviewed(false); setFreshReview(false); setError(""); details.reload();
  };
  const approve = async () => {
    if (!owner || !policy || !reviewed || running.current || freshReview || expired || !supportedPolicy || policy.status !== "pending" || approved) return;
    running.current = true; setBusy("approve"); setError(""); setStatus("");
    try {
      const approval = await api.approveExtensionPairing(policy);
      if (mounted.current) {
        setApproved(true); setApprovalExpiresAt(approval.expires_at); setReviewed(false); grants.reload();
        setStatus(`Owner approval recorded. Return to the extension popup to finish connecting before ${parseDate(approval.expires_at).toLocaleString()}. This website does not reveal a capture credential.`);
      }
    } catch (failure) {
      if (mounted.current) {
        setError(errorMessage(failure));
        if (failure instanceof ApiError && failure.status === 409) { setFreshReview(true); setReviewed(false); }
      }
    } finally { running.current = false; if (mounted.current) setBusy(""); }
  };
  const revoke = async (grant: ExtensionGrant) => {
    if (!owner || running.current || grant.revoked || !confirm(`Revoke jobs:capture access for extension ${grant.extension_id} at ${grant.destination}?`)) return;
    running.current = true; setBusy(grant.grant_id); setError(""); setStatus("");
    try {
      await api.revokeExtensionGrant(grant.grant_id);
      if (mounted.current) { grants.reload(); setStatus("Capture access revoked. New captures under that grant will be rejected."); }
    } catch (failure) { if (mounted.current) setError(errorMessage(failure)); }
    finally { running.current = false; if (mounted.current) setBusy(""); }
  };

  return <div className="stack">
    <div className="topbar"><div><h1>Extension capture access</h1><p>Approve a short-lived capture connection from your signed-in Jobbr website account.</p></div></div>
    {!owner ? <section className="card"><h2>Website owner sign-in required</h2><p>This approval flow requires an authenticated website owner session. An instance token does not authorize this flow. The instance must enable Sign in with ChatGPT before extension owner approval is available.</p></section> : <>
      {requestPath !== undefined && <section className="card stack" aria-busy={details.loading || busy === "approve"}>
        <h2>Review this connection request</h2>
        {!validId ? <p role="alert">This connection request link is invalid. Start a new connection from the extension popup.</p>
          : details.loading ? <p role="status">Loading connection request…</p>
          : details.error ? <div><p role="alert">{errorMessage(details.error)}</p><p className="muted">An expired or consumed request requires starting a new connection in the popup.</p><button className="btn" disabled={!!busy} onClick={refreshDetails}>Retry request details</button></div>
          : policy && <>
            <p>Compare the following details with the extension popup before approving. The Chrome extension ID is reported by the extension; it is not a verified publisher identity.</p>
            <dl className="facts" style={{ overflowWrap: "anywhere" }}>
              <div><dt>Comparison code</dt><dd><strong>{policy.comparison_code}</strong></dd></div>
              <div><dt>Full reported Chrome extension ID</dt><dd><code>{policy.extension_id}</code></dd></div>
              <div><dt>Exact Jobbr destination</dt><dd>{policy.destination}</dd></div>
              <div><dt>Scope</dt><dd>{policy.scope}</dd></div>
              <div><dt>Capture limit</dt><dd>{policy.capture_limit} captures</dd></div>
              <div><dt>Credential lifetime</dt><dd>{policy.token_ttl_seconds / 60} minutes</dd></div>
              <div><dt>Concurrency limit</dt><dd>1 capture at a time</dd></div>
              <div><dt>Connection exchange window</dt><dd>{exchangeDeadline ? `Finish connecting before ${parseDate(exchangeDeadline).toLocaleString()}` : "Approve to start a five-minute exchange window"}</dd></div>
              <div><dt>Exact AI policy</dt><dd>{policy.llm_enabled ? "AI extraction enabled" : "AI extraction disabled"} · {policy.ai_provider === "anthropic" ? "Claude" : "OpenAI"} · {policy.ai_model}</dd></div>
            </dl>
            <p className="muted">This grant permits explicit new-job capture only. It cannot read your profile, notes or existing jobs. The popup asks you to review each captured posting before sending it.</p>
            {policy.llm_enabled ? <p>Captured posting text may be sent to {policy.ai_provider === "anthropic" ? "Claude" : "OpenAI"} ({policy.ai_model}) for extraction and incur API charges. Dollar cost is not estimated. The popup confirms this policy again for each capture; your resume is excluded.</p> : <p>Captures use offline extraction under this policy. Enabling AI or changing the selected provider/model requires a fresh approval.</p>}
            {expired ? <p role="alert">This exchange window has expired. Start a new connection from the extension popup.</p>
              : approved || policy.status === "approved" ? <p role="status">This request has been approved. Return to the extension popup to finish connecting; approval does not submit a posting.</p>
              : !supportedPolicy ? <p role="alert">This request uses an unsupported scope or limit. Approval is disabled; start a new connection with the current extension.</p>
              : <>
                <label className="consent-line"><input type="checkbox" disabled={!!busy || freshReview} checked={reviewed} onChange={event => setReviewed(event.target.checked)} /> I compared the code, full extension ID and destination with my popup. I approve jobs:capture for up to 5 captures over 15 minutes, one at a time, under the exact AI policy above{policy.llm_enabled ? ", including potentially paid posting extraction" : ""}.</label>
                <button className="btn primary" disabled={!!busy || !reviewed || freshReview} onClick={() => void approve()}>{busy === "approve" ? "Approving…" : "Approve this capture connection"}</button>
              </>}
            {freshReview && <p role="alert">Approval settings or request state changed. Load fresh details and compare them again before explicitly approving. Nothing is retried automatically.</p>}
            <button className="btn" disabled={!!busy} onClick={refreshDetails}>Load fresh approval details</button>
          </>}
      </section>}
      <section className="card stack" aria-busy={grants.loading || (!!busy && busy !== "approve")}>
        <header><h2>Capture grants</h2><button className="btn" disabled={!!busy || grants.loading} onClick={grants.reload}>Refresh grants</button></header>
        <p className="muted">Each grant is limited to jobs:capture, 5 captures, 15 minutes and one concurrent capture. Expired grants are omitted. Revoking access does not delete jobs already captured.</p>
        {grants.loading ? <p role="status">Loading capture grants…</p> : grants.error ? <div><p role="alert">{errorMessage(grants.error)}</p><button className="btn" onClick={grants.reload}>Retry grants</button></div> : !visibleGrants.length ? <p>No unexpired capture grants. Start a connection from your extension popup.</p> : <ul className="clean">{visibleGrants.map(grant => <li key={grant.grant_id}>
          <p style={{ overflowWrap: "anywhere" }}><strong>Reported extension ID: {grant.extension_id}</strong><br />Destination: {grant.destination}<br />Scope: jobs:capture · {grant.captures_remaining} captures remaining · expires {parseDate(grant.expires_at).toLocaleString()} · {grant.revoked ? "Revoked" : grant.busy ? "Capture in progress" : grant.captures_remaining === 0 ? "Capture limit reached" : "Ready"}</p>
          <button className="btn danger" disabled={!!busy || grant.revoked} onClick={() => void revoke(grant)}>{busy === grant.grant_id ? "Revoking…" : grant.revoked ? "Access revoked" : "Revoke capture access"}</button>
        </li>)}</ul>}
      </section>
    </>}
    {error && <p role="alert" className="error">{error}</p>}
    {status && <p role="status">{status}</p>}
  </div>;
}
