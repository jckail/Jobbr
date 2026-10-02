import { useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage, getToken } from "../api";
import type { Profile, ResumePreview } from "../types";
import { Chips, Empty, useAsync, useToast } from "../ui";
import { cap, parseDate } from "../util";

const SENIORITY = ["unknown", "intern", "junior", "mid", "senior", "staff", "principal", "manager", "director", "executive"];

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
  const [saveError, setSaveError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [selectedRevision, setSelectedRevision] = useState<number | null>(null);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  const focusedRevision = useRef<number | null>(null);
  const access = useAsync(api.config, []);
  const historyAllowed = !!access.data && (access.data.auth_enabled || (access.data.write_protected && !!getToken()));
  const history = useAsync(() => historyAllowed ? api.profileRevisions() : Promise.resolve([]), [historyAllowed]);
  const revision = useAsync(() => selectedRevision !== null && historyAllowed ? api.profileRevision(selectedRevision) : Promise.resolve(null), [selectedRevision, historyAllowed]);
  useEffect(() => {
    if (selectedRevision === null) focusedRevision.current = null;
    else if (!revision.loading && revision.data?.id === selectedRevision && focusedRevision.current !== selectedRevision) {
      reviewHeading.current?.focus();
      focusedRevision.current = selectedRevision;
    }
  }, [selectedRevision, revision.loading, revision.data?.id]);
  const mounted = useRef(true);
  const saveRunning = useRef(false);
  const previewRunning = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const toast = useToast();
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
  const activeHistoryId = history.data?.find(item => item.active)?.id;
  const reviewedCurrent = activeHistoryId !== undefined && revision.data?.id === activeHistoryId && !revision.loading && !revision.error && !history.loading && !history.error;
  const acceptSaved = (saved: Profile) => {
    setP(saved);
    setLocations(saved.locations.join("; "));
    setTargetTitles(saved.target_titles.join(", "));
    setSaveError(""); setConflict(false);
  };
  const mutationError = (failure: unknown) => {
    setSaveError(errorMessage(failure));
    if (failure instanceof ApiError && failure.status === 409) {
      setConflict(true);
      history.reload();
    }
  };

  async function save() {
    if (saveRunning.current || previewRunning.current) return;
    saveRunning.current = true;
    setBusy(true);
    setSaveError("");
    const { name, headline, resume_text, years_experience, seniority, remote_pref, min_comp, revision_version } = p!;
    try {
      // Send form facts only; skills are derived from the resume server-side.
      const saved = await api.saveProfile({ name, headline, resume_text, years_experience, seniority, remote_pref, min_comp, expected_revision: revision_version, locations: locations.split(";").map((place) => place.trim()).filter(Boolean), target_titles: list(targetTitles) });
      if (mounted.current) {
        acceptSaved(saved); history.reload(); revision.reload(); onChange();
        toast("Saved · every job re-scored");
      }
    } catch (failure) {
      if (mounted.current) mutationError(failure);
    } finally {
      saveRunning.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  async function keepEdits() {
    if (saveRunning.current || previewRunning.current || !reviewedCurrent) return;
    saveRunning.current = true; setBusy(true);
    try {
      const current = await api.profile();
      if (mounted.current) {
        if (current.active_revision_id !== activeHistoryId) {
          setSaveError("The saved profile changed again. Refresh history and review the newest active revision before keeping your edits.");
          history.reload();
          return;
        }
        setP(draft => draft ? { ...draft, active_revision_id: current.active_revision_id, revision_version: current.revision_version } : current);
        setConflict(false); setSaveError(""); history.reload();
        toast("Your form edits remain. Choose Save & re-score to replace the latest saved profile.");
      }
    } catch (failure) { if (mounted.current) mutationError(failure); }
    finally { saveRunning.current = false; if (mounted.current) setBusy(false); }
  }

  async function restoreRevision() {
    const selected = revision.data;
    if (!selected || saveRunning.current || previewRunning.current || !historyAllowed) return;
    if (!confirm(`Restore profile revision #${selected.id} and re-score every job? This replaces any unsaved edits in the form.`)) return;
    saveRunning.current = true; setBusy(true); setSaveError("");
    try {
      const restored = await api.activateProfileRevision(selected.id, p!.revision_version);
      if (mounted.current) {
        acceptSaved(restored); setPreview(null); setUploadMessage("");
        history.reload(); revision.reload(); onChange(); toast("Profile restored · every job re-scored");
      }
    } catch (failure) { if (mounted.current) mutationError(failure); }
    finally { saveRunning.current = false; if (mounted.current) setBusy(false); }
  }

  async function deleteRevision(id: number) {
    if (saveRunning.current || previewRunning.current || !historyAllowed || id === p!.active_revision_id) return;
    if (!confirm(`Delete historical profile revision #${id}? Your active profile is kept.`)) return;
    saveRunning.current = true; setBusy(true); setSaveError("");
    const expectedVersion = p!.revision_version;
    try {
      await api.deleteProfileRevision(id, expectedVersion);
      if (mounted.current) {
        setP(draft => draft ? { ...draft, revision_version: expectedVersion + 1 } : draft);
        if (selectedRevision === id) setSelectedRevision(null);
        history.reload(); toast("Historical profile revision deleted");
      }
    } catch (failure) { if (mounted.current) mutationError(failure); }
    finally { saveRunning.current = false; if (mounted.current) setBusy(false); }
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
      <div className="topbar"><div><h1>Your profile</h1><p>Save your profile to keep a revision and re-score every job.</p></div><button className="btn primary" onClick={save} disabled={busy || uploadBusy || conflict}>{busy ? "Working…" : "Save & re-score"}</button></div>
      {saveError && <p role="alert" className="error">{saveError}</p>}
      {conflict && <section className="card stack"><h2>Review the latest saved profile</h2><p>Your form edits are preserved. Refresh and review the active revision in history below. Keeping your edits updates the save version; your next Save replaces the latest saved profile with this form.</p><div className="resume-actions"><button className="btn" disabled={busy || history.loading} onClick={history.reload}>Refresh history</button><button className="btn" disabled={busy || uploadBusy || !reviewedCurrent} onClick={() => void keepEdits()}>Keep my edits for the next save</button></div></section>}
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
      <section className="card stack" aria-labelledby="profile-history-title" style={{ marginTop: 20 }}>
        <header><h2 id="profile-history-title">Profile history</h2>{historyAllowed && <button className="btn" disabled={busy || history.loading} onClick={history.reload}>Refresh history</button>}</header>
        <p className="muted">Saved revisions are private snapshots. PDF preview and form edits do not add a revision until you save. Restoring activates an earlier snapshot and re-scores your jobs; existing career drafts keep their original text. Up to 50 revisions are retained; delete an older revision when the limit is reached.</p>
        {access.loading ? <p role="status">Checking history access…</p> : access.error ? <div><p role="alert">{errorMessage(access.error)}</p><button className="btn" onClick={access.reload}>Retry access check</button></div>
          : !historyAllowed ? <p>Profile history requires protected access. Open Access to sign in or enter the instance token. An open instance must be configured with access protection.</p>
          : history.loading ? <p role="status">Loading profile history…</p>
          : history.error ? <div><p role="alert">{errorMessage(history.error)}</p><button className="btn" onClick={history.reload}>Retry history</button></div>
          : !history.data?.length ? <p>No saved profile revisions yet.</p>
          : <ul className="clean">{history.data.map(item => <li key={item.id}>
            <p><strong>Revision #{item.id}</strong> · {parseDate(item.saved_at).toLocaleString()} · {item.source === "legacy" ? "Existing profile" : "Saved profile"}{item.active ? " · Active" : ""}</p>
            <div className="resume-actions"><button className="btn" disabled={busy} aria-pressed={selectedRevision === item.id} onClick={() => setSelectedRevision(item.id)}>Review revision #{item.id}</button><button className="btn danger" disabled={busy || item.active || item.id === p.active_revision_id} onClick={() => void deleteRevision(item.id)}>Delete revision #{item.id}</button></div>
          </li>)}</ul>}
        {historyAllowed && selectedRevision !== null && <section className="stack" aria-label={`Review profile revision ${selectedRevision}`}>
          {revision.loading ? <p role="status">Loading revision…</p> : revision.error ? <div><p role="alert">{errorMessage(revision.error)}</p><button className="btn" onClick={revision.reload}>Retry revision</button></div> : revision.data && <>
            <h3 ref={reviewHeading} tabIndex={-1}>Review revision #{revision.data.id}</h3>
            <p className="muted">Saved {parseDate(revision.data.saved_at).toLocaleString()}. Review these facts before restoring; your unsaved form changes will be replaced.</p>
            {revision.data.source === "legacy" && <p className="muted">This existing profile was recorded when history became available; this timestamp does not establish when the resume was originally written.</p>}
            <dl className="facts"><div><dt>Name</dt><dd>{revision.data.snapshot.name}</dd></div><div><dt>Headline</dt><dd>{revision.data.snapshot.headline || "Not set"}</dd></div><div><dt>Level</dt><dd>{cap(revision.data.snapshot.seniority)}</dd></div><div><dt>Experience</dt><dd>{revision.data.snapshot.years_experience == null ? "Not set" : `${revision.data.snapshot.years_experience} years`}</dd></div><div><dt>Work style</dt><dd>{cap(revision.data.snapshot.remote_pref)}</dd></div><div><dt>Minimum pay (USD)</dt><dd>{revision.data.snapshot.min_comp ?? "Not set"}</dd></div><div><dt>Locations</dt><dd>{revision.data.snapshot.locations.join("; ") || "Not set"}</dd></div><div><dt>Target titles</dt><dd>{revision.data.snapshot.target_titles.join(", ") || "Not set"}</dd></div></dl>
            <label className="field">Saved resume text<textarea readOnly rows={10} value={revision.data.snapshot.resume_text} /></label>
            <div><h3>Saved detected skills</h3><Chips items={revision.data.snapshot.skills} kind="have" max={60} /></div>
            <div className="resume-actions"><button className="btn primary" disabled={busy || uploadBusy || conflict || revision.data.id === p.active_revision_id} onClick={() => void restoreRevision()}>{revision.data.id === p.active_revision_id ? "Active saved revision" : `Restore revision #${revision.data.id} & re-score`}</button><button className="btn" disabled={busy} onClick={() => setSelectedRevision(null)}>Close review</button></div>
          </>}
        </section>}
      </section>
    </>
  );
}
