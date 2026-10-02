import { useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage, getToken } from "../api";
import type { AIProvider, CareerKind, CareerResult, Job, SavedCareerDraft } from "../types";
import { useAsync } from "../ui";
import { parseDate } from "../util";

function providerLabel(provider?: AIProvider): string {
  return provider === "anthropic" ? "Claude" : "OpenAI";
}
function printable(result: CareerResult): string {
  const draft = result.draft;
  return [result.kind === "cover_letter" ? "Cover letter — review before sending" : "Interview preparation — review before use",
    draft.cover_letter ?? "", ...draft.interview_questions.map((item, index) => `${index + 1}. ${item.question}\n${item.answer_outline.map((line) => `• ${line}`).join("\n")}\nEvidence: ${item.evidence_quotes.join("; ")}`),
    `Strengths\n${draft.strengths.join("\n")}`, `Gaps\n${draft.gaps.join("\n")}`,
    `Questions to ask\n${draft.questions_to_ask.join("\n")}`, `Profile evidence\n${draft.evidence_quotes.join("\n")}`,
    `Review notes\n${draft.review_notes.join("\n")}`,
    `Provider: ${providerLabel(result.provider)}; model: ${result.model}; input tokens: ${result.input_tokens}; output tokens: ${result.output_tokens}`].filter(Boolean).join("\n\n");
}
function Items({ title, items }: { title: string; items: string[] }) {
  return items.length ? <div><h3>{title}</h3><ul className="clean">{items.map((item, index) => <li key={index}>{item}</li>)}</ul></div> : null;
}
export default function CareerPanel({ job, enabled }: { job: Job; enabled: boolean }) {
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState<CareerKind | null>(null);
  const [result, setResult] = useState<CareerResult | null>(null);
  const [error, setError] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const [savedId, setSavedId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [savedError, setSavedError] = useState("");
  const [savedStatus, setSavedStatus] = useState("");
  const persistenceRunning = useRef(false);
  const access = useAsync(api.config, []);
  const selectedProvider = access.data?.ai_provider;
  const selectedModel = access.data?.ai_model;
  const selectedEnabled = access.data?.llm_enabled;
  const selectedLabel = access.data?.ai_provider_label;
  const generationEnabled = enabled && !!access.data?.career_enabled && !access.loading && !access.error;
  const draftAccess = !!access.data && (access.data.auth_enabled || (access.data.write_protected && !!getToken()));
  const drafts = useAsync(() => draftAccess ? api.careerDrafts(job.id) : Promise.resolve([] as SavedCareerDraft[]), [job.id, draftAccess]);
  const working = busy !== null || saving || deleting !== null;
  const running = useRef(false);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const roleFacts = JSON.stringify([job.title, job.raw_text, job.summary, job.skills, job.nice_to_have, job.responsibilities, job.qualifications]);
  useEffect(() => {
    generation.current += 1; controller.current?.abort(); running.current = false;
    persistenceRunning.current = false;
    setResult(null); setError(""); setCopyStatus(""); setConsent(false); setBusy(null);
    setSavedId(null); setSaving(false); setDeleting(null); setSavedError(""); setSavedStatus("");
    return () => { generation.current += 1; controller.current?.abort(); };
  }, [job.id, roleFacts, selectedProvider, selectedModel, selectedEnabled]);
  const generate = async (kind: CareerKind) => {
    if (!consent || !generationEnabled || running.current || persistenceRunning.current) return;
    running.current = true;
    const attempt = ++generation.current;
    const abort = new AbortController(); controller.current = abort;
    const timeout = window.setTimeout(() => abort.abort(), 130_000);
    setBusy(kind); setError(""); setResult(null); setCopyStatus(""); setSavedId(null); setSavedStatus("");
    try {
      const response = await api.career(job.id, kind, abort.signal, access.data);
      if (attempt === generation.current) setResult(response);
    } catch (failure) {
      if (attempt === generation.current) {
        if (failure instanceof ApiError && failure.status === 409) setConsent(false);
        setError(abort.signal.aborted ? "The request timed out. No result was received; check the server before retrying." : errorMessage(failure));
      }
    } finally {
      window.clearTimeout(timeout);
      if (attempt === generation.current) { running.current = false; setBusy(null); }
    }
  };
  const save = async () => {
    if (!result || savedId !== null || !draftAccess || running.current || persistenceRunning.current) return;
    persistenceRunning.current = true;
    const attempt = generation.current;
    setSaving(true); setSavedError(""); setSavedStatus("");
    try {
      const saved = await api.saveCareerDraft(job.id, result);
      if (attempt === generation.current) {
        setSavedId(saved.id); drafts.reload(); setSavedStatus("Draft saved in this Jobbr instance.");
      }
    } catch (failure) {
      if (attempt === generation.current) setSavedError(errorMessage(failure));
    } finally {
      if (attempt === generation.current) { persistenceRunning.current = false; setSaving(false); }
    }
  };
  const open = (saved: SavedCareerDraft) => {
    if (working) return;
    setResult(saved.result); setSavedId(saved.id); setError(""); setCopyStatus(""); setSavedError("");
    setSavedStatus("Opened a saved draft. It may reflect an earlier profile or posting; review its evidence before use.");
  };
  const remove = async (saved: SavedCareerDraft) => {
    if (running.current || persistenceRunning.current || !confirm("Delete this saved draft from Jobbr?")) return;
    persistenceRunning.current = true;
    const attempt = generation.current;
    setDeleting(saved.id); setSavedError(""); setSavedStatus("");
    try {
      await api.deleteCareerDraft(job.id, saved.id);
      if (attempt === generation.current) {
        if (savedId === saved.id) { setResult(null); setSavedId(null); setCopyStatus(""); }
        drafts.reload(); setSavedStatus("Saved draft deleted.");
      }
    } catch (failure) {
      if (attempt === generation.current) setSavedError(errorMessage(failure));
    } finally {
      if (attempt === generation.current) { persistenceRunning.current = false; setDeleting(null); }
    }
  };
  const copy = async () => {
    if (!result) return;
    try { await navigator.clipboard.writeText(printable(result)); setCopyStatus("Copied draft and review notes."); }
    catch { setCopyStatus("Clipboard unavailable. Download the draft instead."); }
  };
  const download = () => {
    if (!result) return;
    const url = URL.createObjectURL(new Blob([printable(result)], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `jobbr-${job.id}-${result.kind}.txt`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <section className="card career-panel" aria-busy={working}>
    <header><div><h2>Prepare for this role</h2><p className="muted">Draft a letter or practice interview answers from your saved profile.</p></div></header>
    {access.loading ? <p role="status">Checking AI settings…</p> : !generationEnabled ? <p role="status">AI drafting is unavailable{selectedLabel ? ` for ${selectedLabel} (${selectedModel})` : ""}. The instance owner must configure credentials for the selected server provider. Your job tracking, fit scores and protected saved drafts remain available.</p> : <>
      <p className="muted">On your request, Jobbr sends your saved resume excerpt, name, headline, skills, years of experience and seniority, together with this role’s posting and extracted requirements, to {selectedLabel} ({selectedModel}). This may incur API charges; dollar cost is not estimated. <a href="#/profile">Review your saved profile</a> first.</p>
      <label className="consent-line"><input type="checkbox" checked={consent} disabled={working} onChange={(event) => setConsent(event.target.checked)} /> I agree to send those profile and role details to {selectedLabel} ({selectedModel}) for this draft and accept potentially paid API usage.</label>
      <div className="career-actions">
        <button className="btn primary" disabled={!consent || working} onClick={() => generate("cover_letter")}>{busy === "cover_letter" ? "Drafting letter…" : "Draft cover letter"}</button>
        <button className="btn" disabled={!consent || working} onClick={() => generate("interview_prep")}>{busy === "interview_prep" ? "Preparing questions…" : "Prepare for interview"}</button>
      </div>
      {busy && <p role="status">Generating from your saved facts. Review the returned draft before using it.</p>}
    </>}
    {error && <p role="alert" className="career-error">{error}</p>}
    <div className="stack">
      <h3>Saved drafts for this role</h3>
      <p className="muted">Drafts are saved only when you choose Save draft. Reopening uses the saved text and makes no AI request.</p>
      {access.loading ? <p role="status">Checking draft access…</p> : access.error ? <div><p role="alert">{errorMessage(access.error)}</p><button className="btn" onClick={access.reload}>Retry access check</button></div>
        : !draftAccess ? <p>Saving and viewing drafts requires protected access. Open Access to sign in or enter the instance token; an open instance must first be configured with access protection.</p>
        : drafts.loading ? <p role="status">Loading saved drafts…</p>
        : drafts.error ? <div><p role="alert">{errorMessage(drafts.error)}</p><button className="btn" onClick={drafts.reload}>Retry saved drafts</button></div>
        : drafts.data?.length ? <ul className="clean">{drafts.data.map(saved => <li key={saved.id}>
          <p><strong>{saved.result.kind === "cover_letter" ? "Cover letter" : "Interview preparation"}</strong> · {providerLabel(saved.result.provider)} · {saved.result.model} · saved {parseDate(saved.created_at).toLocaleString()}</p>
          <div className="career-actions"><button className="btn" disabled={working} onClick={() => open(saved)} aria-label={`Open ${saved.result.kind === "cover_letter" ? "cover letter" : "interview preparation"} draft saved ${parseDate(saved.created_at).toLocaleString()}`}>Open draft</button><button className="btn danger" disabled={working} onClick={() => void remove(saved)} aria-label={`Delete ${saved.result.kind === "cover_letter" ? "cover letter" : "interview preparation"} draft saved ${parseDate(saved.created_at).toLocaleString()}`}>{deleting === saved.id ? "Deleting…" : "Delete draft"}</button></div>
        </li>)}</ul> : <p>No saved drafts for this role yet.</p>}
      {savedError && <p role="alert" className="career-error">{savedError}</p>}
      {savedStatus && <p role="status">{savedStatus}</p>}
    </div>
    {result && <div className="stack career-result">
      <div className="review-notice" role="note"><strong>Review before use.</strong> Verify every qualification and example against your experience. Jobbr does not send this draft to an employer or change your fit score.</div>
      <div className="career-actions"><button className="btn" onClick={copy}>Copy draft</button><button className="btn" onClick={download}>Download text</button><button className="btn primary" disabled={!draftAccess || working || savedId !== null} onClick={() => void save()}>{saving ? "Saving…" : savedId !== null ? "Draft saved" : "Save draft"}</button></div>
      {copyStatus && <p role="status">{copyStatus}</p>}
      {result.draft.cover_letter && <div className="draft-prose">{result.draft.cover_letter}</div>}
      {result.draft.interview_questions.map((question, index) => <section key={index}>
        <h3>{index + 1}. {question.question}</h3><ul className="clean">{question.answer_outline.map((line, lineIndex) => <li key={lineIndex}>{line}</li>)}</ul>
        <Items title="Supporting profile evidence" items={question.evidence_quotes} />
      </section>)}
      <Items title="Strengths to discuss" items={result.draft.strengths} />
      <Items title="Gaps to prepare for" items={result.draft.gaps} />
      <Items title="Questions to ask the employer" items={result.draft.questions_to_ask} />
      <details><summary>Supporting profile evidence</summary><ul className="clean">{result.draft.evidence_quotes.map((quote, index) => <li key={index}><q>{quote}</q></li>)}</ul></details>
      <Items title="Review notes" items={result.draft.review_notes} />
      <p className="muted">Provider: {providerLabel(result.provider)} · Model: {result.model} · {result.input_tokens.toLocaleString()} input tokens · {result.output_tokens.toLocaleString()} output tokens. Dollar cost is not estimated.</p>
    </div>}
  </section>;
}
