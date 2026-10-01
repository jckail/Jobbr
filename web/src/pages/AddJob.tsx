import { useState } from "react";
import { api, errorMessage } from "../api";
import { Icon, ICONS, Modal, useToast } from "../ui";

export default function AddJob({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [mode, setMode] = useState<"url" | "text">("url");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [company, setCompany] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const toast = useToast();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const j = await api.addJob(mode === "url" ? { url: url.trim() } : { text, company: company.trim() || undefined });
      toast(`Added ${j.title} · match ${j.match?.score ?? "–"}`);
      onDone();
      window.location.hash = `/jobs/${j.id}`;
    } catch (e) {
      const m = errorMessage(e);
      setErr(m);
      if (/paste/i.test(m)) setMode("text");
    } finally { setBusy(false); }
  }

  return (
    <Modal title="Add a job" onClose={onClose}>
      <form onSubmit={submit}>
        <div className="tabs" role="tablist">
          <button type="button" role="tab" aria-selected={mode === "url"} onClick={() => setMode("url")}>From URL</button>
          <button type="button" role="tab" aria-selected={mode === "text"} onClick={() => setMode("text")}>Paste text</button>
        </div>
        {mode === "url" ? (
          <label className="field">Job posting link
            <input type="url" required autoFocus value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://company.com/careers/senior-engineer" />
            <small>Jobbr fetches the page, reads structured data, and scores it against your profile.</small>
          </label>
        ) : (
          <>
            <label className="field">Posting text
              <textarea required autoFocus rows={9} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the full job description…" />
              <small>Use this for pages that need a login or render with JavaScript.</small>
            </label>
            <label className="field">Company <small>optional</small>
              <input type="text" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Acme Inc." />
            </label>
          </>
        )}
        {err && <div role="alert" style={{ color: "var(--low)" }}>{err}</div>}
        <div className="row-end">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}><Icon d={ICONS.plus} />{busy ? "Analysing…" : "Add & score"}</button>
        </div>
      </form>
    </Modal>
  );
}
