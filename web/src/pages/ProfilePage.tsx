import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api";
import type { Profile, ResumePreview } from "../types";
import { Chips, Empty, useAsync, useGuarded } from "../ui";
import { cap } from "../util";

const SENIORITY = ["unknown", "intern", "junior", "mid", "senior", "staff", "principal"];

export default function ProfilePage({ onChange }: { onChange: () => void }) {
  const { data, loading, error, reload } = useAsync(api.profile, []);
  const [p, setP] = useState<Profile | null>(null);
  const [locations, setLocations] = useState("");
  const [targetTitles, setTargetTitles] = useState("");
  const [busy, setBusy] = useState(false);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [preview, setPreview] = useState<ResumePreview | null>(null);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState(false);
  const mounted = useRef(true);
  const saveRunning = useRef(false);
  const previewRunning = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const guarded = useGuarded();
  useEffect(() => {
    if (data) {
      setP(data);
      setLocations(data.locations.join("; "));
      setTargetTitles(data.target_titles.join(", "));
    }
  }, [data]);
  if (!p && (loading || (data && !error))) return <div className="skeleton" style={{ height: 320 }} aria-label="Loading profile" />;
  if (error) return <Empty title="Unable to load your profile"><p role="alert">{errorMessage(error)}</p><button className="btn" onClick={reload} disabled={loading}>{loading ? "Retrying…" : "Try again"}</button></Empty>;
  if (!p) return <Empty title="Your profile is unavailable"><button className="btn" onClick={reload}>Try again</button></Empty>;
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setP({ ...p, [k]: v });
  const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

  async function save() {
    if (saveRunning.current || previewRunning.current) return;
    saveRunning.current = true;
    setBusy(true);
    const { skills: _derived, ...rest } = p!; // skills are re-derived from the resume server-side
    let saved: Profile | undefined;
    const ok = await guarded(async () => { saved = await api.saveProfile({ ...rest, locations: locations.split(";").map((place) => place.trim()).filter(Boolean), target_titles: list(targetTitles) }); },
      "Saved · every job re-scored");
    if (mounted.current && ok && saved) {
      setP(saved);
      setLocations(saved.locations.join("; "));
      setTargetTitles(saved.target_titles.join(", "));
      onChange();
    }
    saveRunning.current = false;
    if (mounted.current) setBusy(false);
  }

  async function previewPdf() {
    if (!resumeFile || previewRunning.current || saveRunning.current) return;
    setPreview(null);
    setUploadError(false);
    if (resumeFile.size > 5 * 1024 * 1024) {
      setUploadMessage("Choose a PDF that is 5 MiB or smaller.");
      setUploadError(true);
      return;
    }
    if (!resumeFile.name.toLowerCase().endsWith(".pdf")) {
      setUploadMessage("Choose a PDF file, or paste plain text in the resume field.");
      setUploadError(true);
      return;
    }
    previewRunning.current = true;
    setUploadBusy(true);
    setUploadMessage("Reading your PDF… Your saved profile is unchanged.");
    try {
      const result = await api.previewResume(resumeFile);
      if (!mounted.current) return;
      setPreview(result);
      setUploadMessage("Review the extracted text, then choose Use this text to replace the resume in the form.");
    } catch (e) {
      if (!mounted.current) return;
      setUploadMessage(errorMessage(e));
      setUploadError(true);
    } finally {
      previewRunning.current = false;
      if (mounted.current) setUploadBusy(false);
    }
  }

  function acceptPreview() {
    if (!preview?.text.trim()) return;
    setP(current => current ? { ...current, resume_text: preview.text } : current);
    setPreview(null);
    setUploadError(false);
    setUploadMessage("Resume text added to the form. Choose Save & re-score to save it.");
  }

  return (
    <>
      <div className="topbar"><div><h1>Your profile</h1><p>Every job is scored against this. Saving re-scores everything instantly.</p></div><button className="btn primary" onClick={save} disabled={busy || uploadBusy}>{busy ? "Saving…" : "Save & re-score"}</button></div>
      <div className="profile">
        <section className="card form">
          <div className="two">
            <label className="field">Name<input type="text" maxLength={200} disabled={busy} value={p.name} onChange={(e) => set("name", e.target.value)} /></label>
            <label className="field">Headline<input type="text" maxLength={300} disabled={busy} value={p.headline ?? ""} onChange={(e) => set("headline", e.target.value)} placeholder="Data & AI engineer" /></label>
          </div>
          <section className="resume-upload" aria-labelledby="resume-upload-title" aria-busy={uploadBusy}>
            <h2 id="resume-upload-title">Import a PDF resume</h2>
            <p className="muted">Up to 5 MiB and 30 pages. Preview sends this PDF to your Jobbr server to read its text. The PDF is not stored; your profile changes only when you save.</p>
            <label className="field">Choose a PDF
              <input type="file" accept=".pdf,application/pdf" disabled={busy || uploadBusy} onChange={e => {
                setResumeFile(e.target.files?.[0] ?? null);
                setPreview(null);
                setUploadMessage("");
                setUploadError(false);
              }} />
            </label>
            <button type="button" className="btn" onClick={previewPdf} disabled={!resumeFile || busy || uploadBusy}>{uploadBusy ? "Reading PDF…" : "Preview PDF text"}</button>
            {uploadMessage && <p role="status" aria-live="polite" className={uploadError ? "resume-message error" : "resume-message"}>{uploadMessage}</p>}
            {preview && <div className="resume-preview">
              <h3>Extracted text</h3>
              <p className="muted">{preview.filename} · {preview.page_count} {preview.page_count === 1 ? "page" : "pages"}. Check names, dates, and formatting before using this text.</p>
              <label className="field">Review and edit the preview
                <textarea rows={10} maxLength={60000} value={preview.text} disabled={busy} onChange={e => setPreview({ ...preview, text: e.target.value })} />
              </label>
              <div className="resume-actions">
                <button type="button" className="btn primary" onClick={acceptPreview} disabled={busy || !preview.text.trim()}>Use this text</button>
                <button type="button" className="btn" disabled={busy} onClick={() => { setPreview(null); setUploadMessage("Preview discarded. Your resume in the form is unchanged."); }}>Discard preview</button>
              </div>
              {p.resume_text && <p className="muted">Using this text replaces the current resume in the form. Your saved resume remains unchanged until you save.</p>}
            </div>}
          </section>
          <label className="field">Resume <small>Paste plain text — skills are detected automatically</small>
            <textarea rows={14} maxLength={60000} disabled={busy} value={p.resume_text} onChange={(e) => set("resume_text", e.target.value)} />
          </label>
        </section>
        <section className="card form">
          <h2>Preferences</h2>
          <div className="two">
            <label className="field">Level<select disabled={busy} value={p.seniority} onChange={(e) => set("seniority", e.target.value)}>{SENIORITY.map((s) => <option key={s} value={s}>{cap(s)}</option>)}</select></label>
            <label className="field">Years of experience<input type="number" disabled={busy} min={0} value={p.years_experience ?? ""} onChange={(e) => set("years_experience", e.target.value ? +e.target.value : null)} /></label>
          </div>
          <div className="two">
            <label className="field">Work style<select disabled={busy} value={p.remote_pref} onChange={(e) => set("remote_pref", e.target.value as Profile["remote_pref"])}><option value="unknown">No preference</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="onsite">On-site</option></select></label>
            <label className="field">Minimum pay (USD)<input type="number" disabled={busy} step={5000} min={0} value={p.min_comp ?? ""} onChange={(e) => set("min_comp", e.target.value ? +e.target.value : null)} /></label>
          </div>
          <label className="field">Locations <small>separate places with semicolons</small><input type="text" disabled={busy} value={locations} onChange={(e) => setLocations(e.target.value)} placeholder="Seattle, WA; New York, NY" /></label>
          <label className="field">Target titles <small>comma separated</small><input type="text" disabled={busy} value={targetTitles} onChange={(e) => setTargetTitles(e.target.value)} /></label>
          <div><h3 style={{ marginBottom: 8 }}>Detected skills ({p.skills.length})</h3>{p.skills.length ? <Chips items={p.skills} kind="have" max={60} /> : <span className="muted">Save to detect skills from your resume.</span>}</div>
        </section>
      </div>
    </>
  );
}
