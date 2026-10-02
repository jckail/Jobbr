import { useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../api";
import { CompanyLogo, Icon, ICONS, Modal, Score, useAsync } from "../ui";

const NAV = [
  ["/", "Overview", ICONS.dash],
  ["/jobs", "Jobs", ICONS.jobs],
  ["/pipeline", "Pipeline", ICONS.board],
  ["/profile", "Profile", ICONS.user],
] as const;

export interface AppShellProps {
  children: ReactNode;
  path: string;
  onAdd: () => void;
  onThemeToggle: () => void;
  authControl?: ReactNode;
  footer?: ReactNode;
  accessAllowed?: boolean;
}

function QuickSearch({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(query), 200);
    return () => window.clearTimeout(timer);
  }, [query]);
  const result = useAsync(() => api.jobs({ q: search, sort: "score" }), [search]);
  return (
    <Modal title="Find your next opportunity" onClose={onClose}>
      <label className="field search-field">Search saved jobs
        <input type="search" placeholder="Job title, company or skill" value={query} onChange={(e) => setQuery(e.target.value)} autoFocus />
      </label>
      <div className="quick-results" aria-live="polite" aria-busy={result.loading}>
        {result.error ? <div className="inline-empty"><p>Jobs couldn’t be loaded.</p><button className="btn" onClick={result.reload}>Try again</button></div>
          : result.loading ? <p className="muted">Searching your jobs…</p>
          : result.data?.length ? result.data.slice(0, 7).map((job) => (
            <a key={job.id} className="quick-result" href={`#/jobs/${job.id}`} onClick={onClose}>
              <CompanyLogo name={job.company.name} size={36} />
              <span><b>{job.title}</b><small>{job.company.name}</small></span>
              <Score value={job.match?.score} size={36} />
            </a>
          )) : <div className="inline-empty"><p>{search ? "No jobs match this search." : "Your saved jobs will appear here."}</p><a href="#/jobs" onClick={onClose}>Explore your jobs</a></div>}
      </div>
      <div className="search-footer"><span>Searches your saved postings</span><kbd>Esc to close</kbd></div>
    </Modal>
  );
}

export default function AppShell({ children, path, onAdd, onThemeToggle, authControl, footer, accessAllowed = false }: AppShellProps) {
  const [searchOpen, setSearchOpen] = useState(false);
  const main = useRef<HTMLElement>(null);
  const active = (to: string) => (to === "/" ? path === "/" : path.startsWith(to)) ? "page" : undefined;
  const label = NAV.find(([to]) => active(to))?.[1] ?? "Workspace";
  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      if (accessAllowed && (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, [accessAllowed]);
  useEffect(() => {
    const heading = main.current?.querySelector("h1");
    if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }); }
    window.scrollTo({ top: 0 });
  }, [path]);
  return (
    <div className="shell">
      <a className="skip-link" href="#main" onClick={(e) => { e.preventDefault(); main.current?.focus(); }}>Skip to content</a>
      <aside className="side">
        <a className="brand" href="#/" aria-label="Jobbr home"><img src="/jobbr/favicon.svg" width="34" height="34" alt="" /><span>Jobbr<span className="brand-dot">.</span></span></a>
        <button className="btn primary side-add" onClick={onAdd}><Icon d={ICONS.plus} />Add job<kbd>N</kbd></button>
        <nav className="nav" aria-label="Main navigation">
          {NAV.map(([to, text, icon]) => <a key={to} href={`#${to}`} aria-current={active(to)}><Icon d={icon} /><span>{text}</span>{active(to) && <span className="nav-indicator" />}</a>)}
        </nav>
        <div className="side-note"><Icon d={ICONS.sparkles} /><p>Your search.<br /><strong>Your next chapter.</strong></p><span>Bring the right opportunities into focus.</span></div>
        <div className="side-foot">
          {authControl && <div className="workspace-access">{authControl}</div>}
          {footer && <div className="workspace-meta">{footer}</div>}
          <div className="side-tools"><a href="#/profile"><Icon d={ICONS.user} />Your profile</a><button className="icon-button" onClick={onThemeToggle} aria-label="Toggle light or dark theme"><Icon d={ICONS.sun} /></button></div>
        </div>
      </aside>
      <div className="workspace">
        <header className="workspace-header">
          <a className="mobile-brand" href="#/" aria-label="Jobbr home"><img src="/jobbr/favicon.svg" alt="" width="30" height="30" /></a>
          <div className="workspace-breadcrumb"><span>Workspace</span><Icon d={ICONS.chevron} /><b>{label}</b></div>
          <button className="workspace-search" disabled={!accessAllowed} onClick={() => accessAllowed && setSearchOpen(true)}><Icon d={ICONS.search} /><span>Search your jobs</span><kbd>⌘ K</kbd></button>
          <div className="workspace-controls"><button className="icon-button mobile-theme" onClick={onThemeToggle} aria-label="Toggle light or dark theme"><Icon d={ICONS.sun} /></button><button className="btn header-add" onClick={onAdd}><Icon d={ICONS.plus} /><span>Add job</span></button></div>
        </header>
        <main className="main" id="main" tabIndex={-1} ref={main}>{children}</main>
        <div className="mobile-access">{authControl}</div>
      </div>
      <nav className="mnav" aria-label="Mobile navigation">
        {NAV.map(([to, text, icon]) => <a key={to} href={`#${to}`} aria-current={active(to)}><Icon d={icon} />{text}</a>)}
        <button onClick={onAdd}><Icon d={ICONS.plus} />Add job</button>
      </nav>
      {searchOpen && accessAllowed && <QuickSearch onClose={() => setSearchOpen(false)} />}
    </div>
  );
}
