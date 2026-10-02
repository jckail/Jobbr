import { useRef, useState, type FormEvent } from "react";
import { api, errorMessage } from "../api";
import type { DiscoveryPosting, DiscoverySnapshot } from "../types";
import { cap } from "../util";
import { useAsync } from "../ui";

export default function DiscoveryPanel({ onSaved }: { onSaved: () => void }) {
  const config = useAsync(api.config, []);
  const [provider, setProvider] = useState<"greenhouse" | "lever">("greenhouse");
  const [board, setBoard] = useState("");
  const [company, setCompany] = useState("");
  const [query, setQuery] = useState("");
  const [remote, setRemote] = useState(false);
  const [snapshot, setSnapshot] = useState<DiscoverySnapshot | null>(null);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<Record<string, number>>({});
  const [error, setError] = useState("");
  const inFlight = useRef(false);

  const search = async (event: FormEvent) => {
    event.preventDefault();
    if (inFlight.current) return;
    inFlight.current = true;
    setSearching(true); setError(""); setSnapshot(null);
    try {
      const [result, jobs] = await Promise.all([
        api.discover(provider, board.trim(), query.trim(), remote ? "remote" : ""),
        api.jobs(),
      ]);
      setSaved(Object.fromEntries(jobs.flatMap((job) => job.url ? [[job.url, job.id]] : [])));
      setSnapshot(result);
    } catch (failure) { setError(errorMessage(failure)); }
    finally { inFlight.current = false; setSearching(false); }
  };

  const save = async (posting: DiscoveryPosting) => {
    if (inFlight.current || config.loading || config.error || !config.data) return;
    const employer = posting.company || company.trim();
    if (!employer) {
      setError("Enter the hiring company name before saving; the board does not provide it.");
      return;
    }
    inFlight.current = true;
    setSaving(posting.url); setError("");
    try {
      const job = await api.addJob({ url: posting.url, text: posting.raw_text, title: posting.title, company: employer }, config.data);
      setSaved((current) => ({ ...current, [posting.url]: job.id }));
      onSaved();
    } catch (failure) { setError(errorMessage(failure)); }
    finally { inFlight.current = false; setSaving(null); }
  };

  return (
    <details className="card discovery-panel">
      <summary><span>Find live opportunities</span><span className="muted">Search a company’s career board</span></summary>
      <p className="muted">Find current openings on Greenhouse or Lever, review the posting, then choose what to save. Nothing is imported automatically.</p>
      {config.loading ? <p role="status">Checking extraction settings…</p> : config.error ? <div><p role="alert">{errorMessage(config.error)}</p><button className="btn" onClick={config.reload}>Retry extraction settings</button></div> : config.data && <p className="muted">{config.data.llm_enabled ? `Saving may send posting text to ${config.data.ai_provider_label} (${config.data.ai_model}) for extraction and incur API charges. Dollar cost is not estimated. Your resume is not included.` : "Saving uses structured posting data and offline heuristics. AI extraction is unavailable for the selected server provider."}</p>}
      <form onSubmit={search} className="stack">
        <div className="grid2">
          <label className="field">Career board provider
            <select value={provider} disabled={searching || saving !== null} onChange={(event) => { setProvider(event.target.value as "greenhouse" | "lever"); setSnapshot(null); }}>
              <option value="greenhouse">Greenhouse</option><option value="lever">Lever</option>
            </select>
          </label>
          <label className="field">Board name
            <input value={board} required maxLength={80} pattern="[A-Za-z0-9][A-Za-z0-9_\-]{0,79}" autoComplete="off" disabled={searching || saving !== null}
              placeholder="Company’s board token, e.g. acme" onChange={(event) => { setBoard(event.target.value); setSnapshot(null); }} />
          </label>
          <label className="field">Hiring company name
            <input value={company} maxLength={200} disabled={searching || saving !== null} placeholder="Required when the board omits it" onChange={(event) => setCompany(event.target.value)} />
          </label>
          <label className="field">Role, skill or keyword
            <input type="search" value={query} maxLength={200} disabled={searching || saving !== null} placeholder="Data engineer, Python…" onChange={(event) => setQuery(event.target.value)} />
          </label>
        </div>
        <div className="discovery-actions">
          <label><input type="checkbox" checked={remote} disabled={searching || saving !== null} onChange={(event) => setRemote(event.target.checked)} /> Remote postings only</label>
          <button className="btn primary" disabled={searching || saving !== null}>{searching ? "Checking career board…" : "Find openings"}</button>
        </div>
      </form>
      {error && <p className="form-error" role="alert">{error}</p>}
      {snapshot && <div className="discovery-results" aria-live="polite">
        <p className="muted">{snapshot.postings.length} openings · {cap(snapshot.provider)} · checked {new Date(snapshot.fetched_at).toLocaleString()}. <a href={snapshot.source_url} target="_blank" rel="noopener noreferrer">View source</a></p>
        <p className="muted">Postings may change after this check. Search again to refresh this snapshot, and review the source before applying.</p>
        {snapshot.truncated && <p className="muted">Only the first 100 postings were checked. Keywords filter that same window; review the company’s board for all openings.</p>}
        {!!snapshot.skipped_unsafe_links && <p className="muted">{snapshot.skipped_unsafe_links} incomplete or unsafe postings were omitted.</p>}
        {!snapshot.postings.length && <p>No openings match in the checked postings. Try different keywords or review the company’s board.</p>}
        {snapshot.postings.map((posting) => <article className="discovery-result" key={posting.source_id}>
          <div><h3>{posting.title}</h3><p className="muted">{posting.company || company || "Hiring company not provided"} · {posting.location || "Location not provided"} · {cap(posting.remote_policy)}</p></div>
          <p>{posting.raw_text.slice(0, 320)}{posting.raw_text.length > 320 ? "…" : ""}</p>
          <div className="discovery-actions">
            <a className="btn" href={posting.url} target="_blank" rel="noopener noreferrer">Review posting</a>
            {saved[posting.url] ? <a className="btn primary" href={`#/jobs/${saved[posting.url]}`}>Open saved role</a> :
              <button className="btn primary" disabled={saving !== null || searching || config.loading || !!config.error || !config.data} onClick={() => void save(posting)}>{saving === posting.url ? "Saving…" : "Save to my jobs"}</button>}
          </div>
        </article>)}
      </div>}
    </details>
  );
}
