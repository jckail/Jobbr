import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "../api";
import type { CareerKind, CareerResult, Job } from "../types";

function printable(result: CareerResult): string {
  const draft = result.draft;
  return [result.kind === "cover_letter" ? "Cover letter — review before sending" : "Interview preparation — review before use",
    draft.cover_letter ?? "", ...draft.interview_questions.map((item, index) => `${index + 1}. ${item.question}\n${item.answer_outline.map((line) => `• ${line}`).join("\n")}\nEvidence: ${item.evidence_quotes.join("; ")}`),
    `Strengths\n${draft.strengths.join("\n")}`, `Gaps\n${draft.gaps.join("\n")}`,
    `Questions to ask\n${draft.questions_to_ask.join("\n")}`, `Profile evidence\n${draft.evidence_quotes.join("\n")}`,
    `Review notes\n${draft.review_notes.join("\n")}`,
    `Model: ${result.model}; input tokens: ${result.input_tokens}; output tokens: ${result.output_tokens}`].filter(Boolean).join("\n\n");
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
  const running = useRef(false);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const roleFacts = JSON.stringify([job.title, job.raw_text, job.summary, job.skills, job.nice_to_have, job.responsibilities, job.qualifications]);
  useEffect(() => {
    generation.current += 1; controller.current?.abort(); running.current = false;
    setResult(null); setError(""); setCopyStatus(""); setConsent(false); setBusy(null);
    return () => { generation.current += 1; controller.current?.abort(); };
  }, [job.id, roleFacts]);
  const generate = async (kind: CareerKind) => {
    if (!consent || !enabled || running.current) return;
    running.current = true;
    const attempt = ++generation.current;
    const abort = new AbortController(); controller.current = abort;
    const timeout = window.setTimeout(() => abort.abort(), 130_000);
    setBusy(kind); setError(""); setResult(null); setCopyStatus("");
    try {
      const response = await api.career(job.id, kind, abort.signal);
      if (attempt === generation.current) setResult(response);
    } catch (failure) {
      if (attempt === generation.current) setError(abort.signal.aborted ? "The request timed out. No result was received; check the server before retrying." : errorMessage(failure));
    } finally {
      window.clearTimeout(timeout);
      if (attempt === generation.current) { running.current = false; setBusy(null); }
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
  return <section className="card career-panel" aria-busy={busy !== null}>
    <header><div><h2>Prepare for this role</h2><p className="muted">Draft a letter or practice interview answers from your saved profile.</p></div></header>
    {!enabled ? <p role="status">AI drafting is unavailable. The instance owner needs to configure a server-side OpenAI API key. Your job tracking and fit scores remain available.</p> : <>
      <p className="muted">On your request, Jobbr sends your saved resume excerpt, name, headline, skills, years of experience and seniority, together with this role’s posting and extracted requirements, to OpenAI. This may use paid API credits. <a href="#/profile">Review your saved profile</a> first.</p>
      <label className="consent-line"><input type="checkbox" checked={consent} disabled={busy !== null} onChange={(event) => setConsent(event.target.checked)} /> I agree to send those profile and role details to OpenAI for this draft.</label>
      <div className="career-actions">
        <button className="btn primary" disabled={!consent || busy !== null} onClick={() => generate("cover_letter")}>{busy === "cover_letter" ? "Drafting letter…" : "Draft cover letter"}</button>
        <button className="btn" disabled={!consent || busy !== null} onClick={() => generate("interview_prep")}>{busy === "interview_prep" ? "Preparing questions…" : "Prepare for interview"}</button>
      </div>
      {busy && <p role="status">Generating from your saved facts. Review the returned draft before using it.</p>}
    </>}
    {error && <p role="alert" className="career-error">{error}</p>}
    {result && <div className="stack career-result">
      <div className="review-notice" role="note"><strong>Review before use.</strong> Verify every qualification and example against your experience. Jobbr does not send this draft to an employer or change your fit score.</div>
      <div className="career-actions"><button className="btn" onClick={copy}>Copy draft</button><button className="btn" onClick={download}>Download text</button></div>
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
      <p className="muted">Model: {result.model} · {result.input_tokens.toLocaleString()} input tokens · {result.output_tokens.toLocaleString()} output tokens. Dollar cost is not estimated.</p>
    </div>}
  </section>;
}
