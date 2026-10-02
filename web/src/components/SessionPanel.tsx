import { useRef, useState } from "react";
import { api, errorMessage, getToken, setToken } from "../api";
import type { AuthSession, Config } from "../types";

interface Props {
  config?: Config;
  session?: AuthSession;
  loading: boolean;
  error?: string;
  onRefresh: () => void;
}

export default function SessionPanel({ config, session, loading, error, onRefresh }: Props) {
  const [token, setValue] = useState(getToken);
  const [busy, setBusy] = useState(false);
  const [actionError, setError] = useState("");
  const running = useRef(false);

  const unlock = async (event: React.FormEvent) => {
    event.preventDefault();
    if (running.current) return;
    running.current = true; setBusy(true); setError("");
    setToken(token.trim());
    try {
      if (config?.private_instance) await api.validateToken();
      onRefresh();
    } catch (failure) {
      setToken("");
      setError(errorMessage(failure));
    } finally { running.current = false; setBusy(false); }
  };
  const logout = async () => {
    if (running.current) return;
    running.current = true; setBusy(true); setError("");
    try { await api.logout(); onRefresh(); }
    catch (failure) { setError(errorMessage(failure)); }
    finally { running.current = false; setBusy(false); }
  };

  return <div className="stack session-panel" aria-busy={loading || busy}>
    <div><h2>Access to Jobbr</h2><p className="muted">Your saved roles and profile stay in this instance.</p></div>
    {loading && <p role="status">Checking access…</p>}
    {error && <div role="alert"><p>{error}</p><button className="btn" onClick={onRefresh} disabled={busy}>Try again</button></div>}
    {!loading && !error && config?.auth_enabled && <>
      {session?.authenticated ? <>
        <p>Signed in as <strong>{session.user?.name || session.user?.email || "the instance owner"}</strong>.</p>
        <div className="career-actions"><button className="btn" disabled={busy} onClick={logout}>{busy ? "Signing out…" : "Sign out of Jobbr"}</button><button className="btn" disabled={busy} onClick={onRefresh}>Refresh access</button></div>
      </> : session?.ready && session.login_url ? <>
        <p>Sign in with the authorized owner’s ChatGPT account to continue.</p>
        <a className="btn primary" href={session.login_url}>Continue with ChatGPT</a>
      </> : <>
        <p role="status">{session?.reason || "Sign in with ChatGPT is unavailable for this instance."}</p>
        <p className="muted">The instance owner must complete OpenAI website client registration and server configuration.</p>
      </>}
    </>}
    {!loading && !error && config && !config.auth_enabled && config.write_protected && <form className="stack" onSubmit={unlock}>
      <p className="muted">{config.private_instance ? "Enter the instance access token to view and edit your workspace." : "Viewing is public. Enter the instance token to enable editing; the server checks it on each write."} The token is kept only for this browser tab’s session.</p>
      <label className="field">Instance access token<input type="password" autoComplete="off" value={token} onChange={(event) => setValue(event.target.value)} disabled={busy} /></label>
      <div className="actions"><button className="btn primary" disabled={busy || !token.trim()}>{busy ? "Checking…" : "Unlock access"}</button>
        <button className="btn" type="button" disabled={busy} onClick={() => { setToken(""); setValue(""); onRefresh(); }}>Clear token</button></div>
    </form>}
    {!loading && !error && config && !config.auth_enabled && !config.write_protected && <p>This instance has open access. Keep private resume information in an instance configured with access protection.</p>}
    {actionError && <p role="alert" className="error">{actionError}</p>}
  </div>;
}
