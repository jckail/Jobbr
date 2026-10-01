import { useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";
import AddJob from "./pages/AddJob";
import Dashboard from "./pages/Dashboard";
import JobDetail from "./pages/JobDetail";
import Jobs from "./pages/Jobs";
import Pipeline from "./pages/Pipeline";
import ProfilePage from "./pages/ProfilePage";
import { Icon, ICONS, Modal, ToastProvider, useAsync, useRoute } from "./ui";

const NAV = [
  ["/", "Overview", ICONS.dash], ["/jobs", "Jobs", ICONS.jobs], ["/pipeline", "Pipeline", ICONS.board], ["/profile", "Profile", ICONS.user],
] as const;

function Shell() {
  const [route] = useRoute();
  const [adding, setAdding] = useState(false);
  const [tokenOpen, setTokenOpen] = useState(false);
  const [rev, setRev] = useState(0); // bump to refetch after mutations
  const cfg = useAsync(api.config, []);
  const [theme, setTheme] = useState<string>(() => { try { return localStorage.getItem("jobbr.theme") ?? ""; } catch { return ""; } });
  useEffect(() => {
    const dark = theme ? theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try { if (theme) localStorage.setItem("jobbr.theme", theme); } catch { /* */ }
  }, [theme]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "n" && !/INPUT|TEXTAREA|SELECT/.test((e.target as HTMLElement).tagName) && !e.metaKey && !e.ctrlKey) { e.preventDefault(); setAdding(true); } };
    window.addEventListener("keydown", h); return () => window.removeEventListener("keydown", h);
  }, []);

  const path = route.split("?")[0] ?? "/";
  const bump = () => setRev((x) => x + 1);
  const jobId = /^\/jobs\/(\d+)$/.exec(path)?.[1];
  let page;
  if (jobId) page = <JobDetail id={+jobId} rev={rev} onChange={bump} />;
  else if (path === "/jobs") page = <Jobs rev={rev} onAdd={() => setAdding(true)} />;
  else if (path === "/pipeline") page = <Pipeline rev={rev} onChange={bump} />;
  else if (path === "/profile") page = <ProfilePage onChange={bump} />;
  else page = <Dashboard rev={rev} onAdd={() => setAdding(true)} llm={cfg.data?.llm_enabled} />;

  const active = (to: string) => (to === "/" ? path === "/" : path.startsWith(to)) ? "page" : undefined;
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand"><div className="logo">J</div>Jobbr</div>
        <button className="btn primary" onClick={() => setAdding(true)}><Icon d={ICONS.plus} />Add job <kbd style={{ marginLeft: "auto", opacity: .7 }}>N</kbd></button>
        <nav className="nav" style={{ marginTop: 10 }} aria-label="Main">
          {NAV.map(([to, label, ic]) => <a key={to} href={`#${to}`} aria-current={active(to)}><Icon d={ic} />{label}</a>)}
        </nav>
        <div className="side-foot">
          <div>{cfg.data?.llm_enabled ? <>✦ AI extraction · <span title={cfg.data.model ?? ""}>{cfg.data.model?.split("-").slice(1, 3).join(" ")}</span></> : "Heuristic extraction (no AI key set)"}</div>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn ghost" style={{ padding: "4px 8px" }} onClick={() => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark")} aria-label="Toggle theme"><Icon d={ICONS.sun} /></button>
            {cfg.data?.write_protected && <button className="btn ghost" style={{ padding: "4px 8px" }} onClick={() => setTokenOpen(true)}>{getToken() ? "🔓 Editing" : "🔒 Read-only"}</button>}
          </div>
          <div>v{cfg.data?.version}</div>
        </div>
      </aside>
      <main className="main" id="main">{page}</main>
      <nav className="mnav" aria-label="Main mobile">
        {NAV.map(([to, label, ic]) => <a key={to} href={`#${to}`} aria-current={active(to)}><Icon d={ic} />{label}</a>)}
        <a href="#/" onClick={(e) => { e.preventDefault(); setAdding(true); }}><Icon d={ICONS.plus} />Add</a>
      </nav>
      {adding && <AddJob onClose={() => setAdding(false)} onDone={() => { setAdding(false); bump(); }} />}
      {tokenOpen && <TokenDialog onClose={() => setTokenOpen(false)} />}
    </div>
  );
}

function TokenDialog({ onClose }: { onClose: () => void }) {
  const [v, setV] = useState(getToken());
  return (
    <Modal title="Unlock editing" onClose={onClose}>
      <form onSubmit={(e) => { e.preventDefault(); setToken(v.trim()); onClose(); }}>
        <p className="muted" style={{ margin: 0 }}>This instance is public read-only. Enter the access token to add or edit jobs.</p>
        <input type="password" value={v} onChange={(e) => setV(e.target.value)} placeholder="Access token" autoFocus style={{ width: "100%", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: "9px 12px" }} />
        <div className="row-end"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn primary">Save</button></div>
      </form>
    </Modal>
  );
}

export default function App() {
  return <ToastProvider><Shell /></ToastProvider>;
}
