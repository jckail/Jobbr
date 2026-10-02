import { useEffect, useState } from "react";
import { api, clearSession, errorMessage, getToken, setToken } from "./api";
import AppShell from "./components/AppShell";
import SessionPanel from "./components/SessionPanel";
import AddJob from "./pages/AddJob";
import Dashboard from "./pages/Dashboard";
import JobDetail from "./pages/JobDetail";
import Jobs from "./pages/Jobs";
import Pipeline from "./pages/Pipeline";
import ProfilePage from "./pages/ProfilePage";
import type { AuthSession, Config } from "./types";
import { Modal, ToastProvider, useRoute } from "./ui";

type Access = { loading: boolean; config?: Config; session?: AuthSession; tokenValidated: boolean; error?: string };

function Shell() {
  const [route] = useRoute();
  const [adding, setAdding] = useState(false);
  const [accessOpen, setAccessOpen] = useState(false);
  const [rev, setRev] = useState(0);
  const [accessRevision, setAccessRevision] = useState(0);
  const [access, setAccess] = useState<Access>({ loading: true, tokenValidated: false });
  const [theme, setTheme] = useState<string>(() => { try { return localStorage.getItem("jobbr.theme") ?? ""; } catch { return ""; } });
  const refresh = () => {
    setAccess((previous) => ({ ...previous, loading: true, tokenValidated: false, error: undefined }));
    setAccessRevision((value) => value + 1);
    setRev((value) => value + 1);
  };
  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const [config, session] = await Promise.all([api.config(), api.session()]);
        let tokenValidated = false;
        if (!config.auth_enabled && config.private_instance && getToken()) {
          try { await api.validateToken(); tokenValidated = true; }
          catch { setToken(""); }
        }
        if (live) setAccess({ loading: false, config, session, tokenValidated });
      } catch (failure) {
        clearSession();
        if (live) setAccess({ loading: false, tokenValidated: false, error: errorMessage(failure) });
      }
    };
    void load();
    return () => { live = false; };
  }, [accessRevision]);
  useEffect(() => {
    const expired = () => {
      clearSession();
      setAccess((previous) => ({ ...previous, loading: true, tokenValidated: false, session: undefined }));
      setAccessRevision((value) => value + 1);
    };
    window.addEventListener("jobbr:access-expired", expired);
    return () => window.removeEventListener("jobbr:access-expired", expired);
  }, []);
  useEffect(() => {
    const dark = theme ? theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try { if (theme) localStorage.setItem("jobbr.theme", theme); } catch { /* unavailable storage */ }
  }, [theme]);

  const config = access.config;
  const allowed = !access.loading && !access.error && !!config && (config.auth_enabled
    ? !!access.session?.authenticated
    : !config.private_instance || access.tokenValidated);
  useEffect(() => {
    if (!allowed) return;
    const handler = (event: KeyboardEvent) => {
      if (document.querySelector('[role="dialog"][aria-modal="true"]')) return;
      if (event.key === "n" && !/INPUT|TEXTAREA|SELECT/.test((event.target as HTMLElement).tagName) && !event.metaKey && !event.ctrlKey) {
        event.preventDefault(); setAdding(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [allowed]);

  const path = route.split("?")[0] ?? "/";
  const bump = () => setRev((value) => value + 1);
  const jobId = /^\/jobs\/(\d+)$/.exec(path)?.[1];
  const panel = <SessionPanel config={config} session={access.session} loading={access.loading} error={access.error} onRefresh={refresh} />;
  let page;
  if (!allowed) page = <section className="card access-gate">{panel}</section>;
  else if (jobId) page = <JobDetail key={jobId} id={+jobId} rev={rev} onChange={bump} llmEnabled={config?.llm_enabled ?? false} />;
  else if (path === "/jobs") page = <Jobs rev={rev} onAdd={() => setAdding(true)} />;
  else if (path === "/pipeline") page = <Pipeline rev={rev} onChange={bump} />;
  else if (path === "/profile") page = <ProfilePage onChange={bump} />;
  else page = <Dashboard rev={rev} onAdd={() => setAdding(true)} llm={config?.llm_enabled} />;
  const accessLabel = config?.auth_enabled ? access.session?.authenticated ? "Account" : "Sign in" : "Access";

  return <>
    <AppShell path={path} accessAllowed={allowed} onAdd={() => allowed ? setAdding(true) : setAccessOpen(true)}
      onThemeToggle={() => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark")}
      authControl={<button className="btn ghost" onClick={() => setAccessOpen(true)}>{accessLabel}</button>}
      footer={<><div>{config?.llm_enabled ? "OpenAI extraction enabled" : "Deterministic extraction"}</div><div>{config ? `v${config.version}` : "Checking connection"}</div></>}>
      {page}
    </AppShell>
    {adding && allowed && <AddJob onClose={() => setAdding(false)} onDone={() => { setAdding(false); bump(); }} />}
    {accessOpen && <Modal title="Workspace access" onClose={() => setAccessOpen(false)}>{panel}</Modal>}
  </>;
}

export default function App() {
  return <ToastProvider><Shell /></ToastProvider>;
}
