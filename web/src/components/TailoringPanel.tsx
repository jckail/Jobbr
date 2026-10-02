import { useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage, getToken } from "../api";
import type { Config, SavedTailoringDraft, TailoringDraft, TailoringResult } from "../types";
import { useAsync } from "../ui";
import { cap, parseDate } from "../util";

function providerName(result: TailoringResult) {
  return result.provider === "anthropic" ? "Claude" : "OpenAI";
}

function printable(result: TailoringResult, draft: TailoringDraft) {
  return ["Tailored resume — review every claim before use", draft.resume_text,
    "Proposed changes", ...draft.changes.map(change => `${change.description}\nEvidence: ${change.evidence_quotes.join("; ")}`),
    "Unresolved gaps", ...draft.gaps, "Review notes", ...draft.review_notes,
    `Source profile revision: ${result.source.revision_id}; job: ${result.source.job_id}`,
    `Job input fingerprint: ${result.source.job_fingerprint}`,
    `Provider: ${providerName(result)}; model: ${result.model}; generated: ${result.generated_at}`,
    `Input tokens: ${result.input_tokens}; output tokens: ${result.output_tokens}`,
    "Edited text is reviewed user content; its claims are not certified by Jobbr."].join("\n\n");
}

export default function TailoringPanel({ jobId, config, onChange }: { jobId: number; config?: Config; onChange: () => void }) {
  const privateAccess = !!config && (config.auth_enabled || (config.write_protected && !!getToken()));
  const current = useAsync(() => privateAccess ? api.profile() : Promise.resolve(null), [privateAccess]);
  const revisions = useAsync(() => privateAccess ? api.profileRevisions() : Promise.resolve([]), [privateAccess]);
  const saved = useAsync(() => privateAccess ? api.tailoringDrafts(jobId) : Promise.resolve([]), [jobId, privateAccess]);
  const [sourceId, setSourceId] = useState<number | null>(null);
  const source = useAsync(() => privateAccess && sourceId !== null ? api.profileRevision(sourceId) : Promise.resolve(null), [privateAccess, sourceId]);
  const [consent, setConsent] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [result, setResult] = useState<TailoringResult | null>(null);
  const [draft, setDraft] = useState<TailoringDraft | null>(null);
  const [savedId, setSavedId] = useState<number | null>(null);
  const [expectedVersion, setExpectedVersion] = useState<number | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [conflict, setConflict] = useState(false);
  const [reviewActive, setReviewActive] = useState(false);
  const running = useRef(false);
  const lifecycle = useRef(0);
  const abort = useRef<AbortController | null>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (sourceId === null && current.data) setSourceId(current.data.active_revision_id);
  }, [sourceId, current.data]);
  useEffect(() => { setConsent(false); }, [config?.ai_provider, config?.ai_model, config?.llm_enabled, sourceId]);
  useEffect(() => () => { lifecycle.current += 1; abort.current?.abort(); }, [jobId]);
  useEffect(() => { if (result) resultHeading.current?.focus(); }, [result]);

  async function act<T>(label: string, request: () => Promise<T>, success: (value: T) => void) {
    if (running.current) return;
    running.current = true;
    const attempt = lifecycle.current;
    setBusy(label); setError(""); setStatus("");
    try {
      const value = await request();
      if (attempt === lifecycle.current) success(value);
    } catch (failure) {
      if (attempt === lifecycle.current) {
        if (failure instanceof ApiError && failure.status === 409) {
          if (label === "Generating") setConsent(false);
          if (label === "Accepting") { setConflict(true); setReviewActive(false); }
        }
        setError(failure instanceof DOMException && failure.name === "AbortError"
          ? label === "Generating"
            ? "Generation timed out or was cancelled. Your active profile is unchanged; no request is retried automatically."
            : "The request was cancelled. Its outcome is unknown; check the current profile and saved proposals before retrying. No request is retried automatically."
          : errorMessage(failure));
      }
    } finally {
      if (attempt === lifecycle.current) { running.current = false; setBusy(""); }
    }
  }

  const generate = async () => {
    if (running.current || !privateAccess || !config?.career_enabled || !consent || sourceId === null || source.data?.id !== sourceId || source.loading || source.error || current.loading || current.error || !current.data) return;
    if (result && !confirm("Generate another proposal? This replaces the proposal currently open here. Save or copy it first if you want to keep it.")) return;
    const version = current.data.revision_version;
    await act("Generating", async () => {
      const controller = new AbortController(); abort.current = controller;
      const timeout = window.setTimeout(() => controller.abort(), 130_000);
      try { return await api.tailorResume(jobId, sourceId, config, controller.signal); }
      finally { window.clearTimeout(timeout); }
    }, response => {
      setResult(response); setDraft(response.draft); setSavedId(null); setReviewed(false);
      setExpectedVersion(version); setConflict(false); setReviewActive(false);
      setStatus(`Generated from revision #${response.source.revision_id}. Your active profile is unchanged.`);
    });
  };
  const saveDraft = async () => {
    if (!result || !draft || !reviewed || savedId !== null || !privateAccess) return;
    await act("Saving", () => api.saveTailoringDraft(jobId, result.receipt_id, draft), response => {
      setResult(response); setDraft(response.draft); setSavedId(response.id); saved.reload();
      setStatus(`Draft saved from revision #${response.source.revision_id}. Saving does not activate it or change your current profile.`);
    });
  };
  const open = async (item: SavedTailoringDraft) => {
    if (!current.data) return;
    if (result && savedId === null && !confirm("Open this saved draft and replace the unsaved proposal here? Copy or save the proposal first to keep it.")) return;
    const version = current.data.revision_version;
    await act("Opening", () => api.tailoringDraft(jobId, item.id), response => {
      setResult(response); setDraft(response.draft); setSavedId(response.id); setReviewed(false);
      setExpectedVersion(version); setConflict(false); setReviewActive(false);
      setStatus("Saved draft opened without an AI request. Review the resume and evidence before accepting it.");
    });
  };
  const remove = async (item: SavedTailoringDraft) => {
    if (!confirm(`Delete saved tailored resume #${item.id}? This does not change the active profile.`)) return;
    await act("Deleting", () => api.deleteTailoringDraft(jobId, item.id), () => {
      if (savedId === item.id) setSavedId(null);
      saved.reload(); setStatus("Saved tailoring draft deleted. Your active profile is unchanged.");
    });
  };
  const accept = async () => {
    if (savedId === null || expectedVersion === null || !reviewed || conflict) return;
    if (!confirm("Activate this exact saved resume and re-score every job? It replaces the current resume and detected skills. Current identity, headline, experience and preferences are kept.")) return;
    await act("Accepting", () => api.acceptTailoringDraft(jobId, savedId, expectedVersion), response => {
      setExpectedVersion(response.revision_version); current.reload(); revisions.reload(); onChange();
      setStatus(`Tailored resume activated as profile revision #${response.active_revision_id}. Every job was re-scored.`);
    });
  };
  const copy = async () => {
    if (!result || !draft) return;
    try { await navigator.clipboard.writeText(printable(result, draft)); setStatus("Copied resume, evidence and review notes."); }
    catch { setStatus("Clipboard unavailable. Download the text instead."); }
  };
  const download = () => {
    if (!result || !draft) return;
    const url = URL.createObjectURL(new Blob([printable(result, draft)], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = `jobbr-${jobId}-tailored-resume.txt`; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return <section className="card stack" aria-busy={!!busy}>
    <header><h2>Tailor your resume for this role</h2></header>
    <p className="muted">Generate a proposal from a saved profile revision. Review and save it first; activating it is a separate action that changes your saved resume and re-scores jobs.</p>
    {!config ? <p role="status">Checking workspace settings…</p> : !privateAccess ? <p>Resume tailoring and saved proposals require protected access. Open Access to sign in or enter the instance token. An open instance must first be configured with access protection.</p> : <>
      {revisions.loading || current.loading ? <p role="status">Loading saved profiles…</p> : revisions.error || current.error ? <div><p role="alert">{errorMessage(revisions.error ?? current.error)}</p><button className="btn" onClick={() => { revisions.reload(); current.reload(); }}>Retry saved profiles</button></div>
        : !revisions.data?.length ? <p>Save your resume in <a href="#/profile">your profile</a> before tailoring it.</p> : <>
          <label className="field">Profile revision used for generation<select disabled={!!busy} value={sourceId ?? ""} onChange={event => setSourceId(Number(event.target.value))}>{revisions.data.map(item => <option key={item.id} value={item.id}>Revision #{item.id} · {parseDate(item.saved_at).toLocaleString()}{item.active ? " · Active" : ""}</option>)}</select></label>
          {source.loading ? <p role="status">Loading source revision…</p> : source.error ? <div><p role="alert">{errorMessage(source.error)}</p><button className="btn" onClick={source.reload}>Retry source revision</button></div> : source.data && <details><summary>Review source revision #{source.data.id}</summary><p>{source.data.snapshot.name} · {source.data.snapshot.headline || "No headline"}</p><label className="field">Source resume<textarea readOnly rows={8} value={source.data.snapshot.resume_text} /></label></details>}
          {!config.career_enabled ? <p role="status">Tailoring is unavailable for {config.ai_provider_label} ({config.ai_model}). Configure the selected provider’s credentials on the server. Existing saved proposals remain available.</p> : <>
            <p className="muted">On your request, profile facts and the complete resume from selected revision #{sourceId}, plus this job’s posting and requirements, are sent to {config.ai_provider_label} ({config.ai_model}). This may incur API charges; dollar cost is not estimated. Application notes are excluded.</p>
            <label className="consent-line"><input type="checkbox" checked={consent} disabled={!!busy} onChange={event => setConsent(event.target.checked)} /> I agree to send this revision’s profile and resume facts to {config.ai_provider_label} ({config.ai_model}) for potentially paid tailoring.</label>
            <button className="btn primary" disabled={!!busy || !consent || source.loading || !!source.error || source.data?.id !== sourceId} onClick={() => void generate()}>{busy === "Generating" ? "Generating proposal…" : "Generate resume proposal"}</button>
          </>}
        </>}
      <div className="stack"><header><h3>Saved resume proposals</h3><button className="btn" disabled={!!busy || saved.loading} onClick={saved.reload}>Refresh proposals</button></header>
        {saved.loading ? <p role="status">Loading saved proposals…</p> : saved.error ? <div><p role="alert">{errorMessage(saved.error)}</p><button className="btn" onClick={saved.reload}>Retry saved proposals</button></div> : !saved.data?.length ? <p>No saved resume proposals for this role yet.</p> : <ul className="clean">{saved.data.map(item => <li key={item.id}><p><strong>Proposal #{item.id}</strong> · source revision #{item.source.revision_id} · {providerName(item)} ({item.model}) · {parseDate(item.created_at).toLocaleString()}{item.user_edited ? " · Edited user content" : ""}</p><div className="resume-actions"><button className="btn" disabled={!!busy || current.loading || !!current.error || !current.data} onClick={() => void open(item)}>Open proposal #{item.id}</button><button className="btn danger" disabled={!!busy} onClick={() => void remove(item)}>Delete proposal #{item.id}</button></div></li>)}</ul>}
      </div>
    </>}
    {busy && <p role="status">{busy}…</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {status && <p role="status">{status}</p>}
    {privateAccess && result && draft && <div className="stack">
      <h3 ref={resultHeading} tabIndex={-1}>Review proposed resume</h3>
      <p className="muted">Source revision #{result.source.revision_id} · {providerName(result)} ({result.model}) · generated {parseDate(result.generated_at).toLocaleString()} · {result.input_tokens.toLocaleString()} input / {result.output_tokens.toLocaleString()} output tokens. Dollar cost is not estimated.</p>
      <div className="review-notice"><strong>Review every claim.</strong> Evidence supports the original proposal; edits are user content and are not certified by Jobbr. Source revision #{result.source.revision_id} remains the generation source even if another profile becomes active.</div>
      <label className="field">Review and edit resume text<textarea rows={14} maxLength={60000} disabled={!!busy} value={draft.resume_text} onChange={event => { setDraft({ ...draft, resume_text: event.target.value }); setSavedId(null); setReviewed(false); }} /></label>
      <div><h3>Proposed changes and source evidence</h3><ul className="clean">{draft.changes.map((change, index) => <li key={index}><p>{change.description}</p><ul>{change.evidence_quotes.map((quote, quoteIndex) => <li key={quoteIndex}><q>{quote}</q></li>)}</ul></li>)}</ul></div>
      <div><h3>Unresolved gaps</h3>{draft.gaps.length ? <ul>{draft.gaps.map((gap, index) => <li key={index}>{gap}</li>)}</ul> : <p>No gaps were returned; still verify every qualification.</p>}</div>
      <div><h3>Review notes</h3><ul>{draft.review_notes.map((note, index) => <li key={index}>{note}</li>)}</ul></div>
      <label className="consent-line"><input type="checkbox" checked={reviewed} disabled={!!busy} onChange={event => setReviewed(event.target.checked)} /> I reviewed this resume, its evidence and gaps, and verified its claims against my experience.</label>
      <div className="resume-actions"><button className="btn" onClick={() => void copy()}>Copy proposal</button><button className="btn" onClick={download}>Download text</button><button className="btn primary" disabled={!!busy || !reviewed || !draft.resume_text.trim() || savedId !== null} onClick={() => void saveDraft()}>{busy === "Saving" ? "Saving…" : savedId === null ? "Save reviewed proposal" : "Proposal saved"}</button><button className="btn primary" disabled={!!busy || !reviewed || savedId === null || expectedVersion === null || conflict} onClick={() => void accept()}>{busy === "Accepting" ? "Activating…" : "Activate saved resume & re-score"}</button></div>
      <p className="muted">Saving keeps a private draft and does not change the active profile. Activation uses the exact saved text and updates only the resume and detected skills; current identity, headline, experience and preferences are kept. Generation receipts expire after seven days; a saved proposal remains usable afterward.</p>
      {conflict && <section className="stack"><h3>Review the current profile before retrying</h3><p>Your proposal and saved draft remain unchanged. Review the current active profile before explicitly allowing this proposal to replace its resume.</p><button className="btn" disabled={!!busy || current.loading} onClick={() => { setReviewActive(true); current.reload(); }}>Load current profile for review</button>
        {reviewActive && (current.loading ? <p role="status">Loading current profile…</p> : current.error ? <p role="alert">{errorMessage(current.error)}</p> : current.data && <>
          <p><strong>Current revision #{current.data.active_revision_id}</strong> · {current.data.name} · {current.data.headline || "No headline"}</p>
          <p>{cap(current.data.seniority)} · {current.data.years_experience ?? "Unspecified"} years · {cap(current.data.remote_pref)} · {current.data.locations.join("; ") || "No locations"} · minimum USD {current.data.min_comp ?? "not set"} · targets {current.data.target_titles.join(", ") || "not set"}</p>
          <label className="field">Current saved resume<textarea rows={8} readOnly value={current.data.resume_text} /></label>
          <button className="btn" disabled={!!busy} onClick={() => { setExpectedVersion(current.data!.revision_version); setConflict(false); setReviewActive(false); setReviewed(false); setError(""); setStatus("Current profile reviewed. Review the proposal again, then explicitly activate it to replace only the current resume."); }}>Use this reviewed profile version for acceptance</button>
        </>)}
      </section>}
    </div>}
  </section>;
}
