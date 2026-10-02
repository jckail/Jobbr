import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import CareerPanel from "../components/CareerPanel";
import { STAGES, type Stage } from "../types";
import { Chips, CompanyLogo, Empty, Icon, ICONS, Score, StagePill, useAsync, useGuarded } from "../ui";
import { ago, cap, comp } from "../util";

function localDate(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value + "Z");
  if (!Number.isFinite(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export default function JobDetail({ id, rev, onChange, llmEnabled }: { id: number; rev: number; onChange: () => void; llmEnabled: boolean }) {
  const { data: j, loading, error, reload } = useAsync(() => api.job(id), [id, rev]);
  const [notes, setNotes] = useState("");
  const [reminder, setReminder] = useState("");
  const [savingReminder, setSavingReminder] = useState(false);
  const nextStep = j?.application.next_step_at;
  useEffect(() => { setReminder(localDate(nextStep)); }, [id, nextStep]);
  const guarded = useGuarded();
  const savedNotes = j?.application.notes ?? "";
  useEffect(() => { setNotes(savedNotes); }, [j?.id, savedNotes]);

  if (loading && !j) return <div className="skeleton" style={{ height: 360 }} />;
  if (error) return <Empty title="Unable to load this role"><p>{errorMessage(error)}</p><button className="btn" onClick={reload}>Try again</button> <a href="#/jobs">Back to jobs</a></Empty>;
  if (!j) return <Empty title="Job not found"><a href="#/jobs">Back to jobs</a></Empty>;

  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    if (await guarded(fn, ok)) { onChange(); reload(); }
  };
  const m = j.match;
  const w: Record<string, string> = { skills: "Skills", seniority: "Level", location: "Location", comp: "Pay" };

  return (
    <>
      <p style={{ margin: "0 0 14px" }}><a href="#/jobs">← All jobs</a></p>
      <div className="detail">
        <div className="stack">
          <section className="card">
            <div className="hero">
              <CompanyLogo name={j.company.name} size={52} />
              <div className="grow"><h1>{j.title}</h1><div className="muted">{j.company.name}{j.company.industry ? ` · ${j.company.industry}` : ""} · added {ago(j.first_seen_at)}</div></div>
              <Score value={m?.score} size={68} />
            </div>
            {j.ai_take && <p style={{ margin: "16px 0 0", padding: "10px 14px", background: "var(--accent-soft)", borderRadius: 10 }}>✦ {j.ai_take}</p>}
            <dl className="facts" style={{ margin: "18px 0 0" }}>
              <div><dt>Pay</dt><dd>{comp(j.comp_min, j.comp_max)}</dd></div>
              <div><dt>Work style</dt><dd>{cap(j.remote_policy)}</dd></div>
              <div><dt>Location</dt><dd>{j.locations.join(" · ") || "—"}</dd></div>
              <div><dt>Level</dt><dd>{cap(j.seniority)}{j.years_experience_min ? ` · ${j.years_experience_min}+ yrs` : ""}</dd></div>
            </dl>
            <div style={{ display: "flex", gap: 8, marginTop: 18, flexWrap: "wrap" }}>
              {j.url && <a className="btn primary" href={j.url} target="_blank" rel="noreferrer noopener"><Icon d={ICONS.ext} />Open posting</a>}
              <button className="btn" onClick={() => run(() => api.reextract(j.id), "Re-extracted")}><Icon d={ICONS.refresh} />Re-extract</button>
              <button className="btn danger" onClick={() => confirm("Delete this job?") && run(async () => { await api.deleteJob(j.id); window.location.hash = "/jobs"; }, "Deleted")}><Icon d={ICONS.trash} />Delete</button>
            </div>
          </section>

          <CareerPanel job={j} enabled={llmEnabled} />
          {j.summary && <section className="card"><header><h2>About the role</h2></header><p style={{ margin: 0 }}>{j.summary}</p></section>}
          <section className="card"><header><h2>Skills</h2></header>
            <h3 style={{ marginBottom: 8 }}>Required</h3><Chips items={j.skills} max={40} kind="accent" />
            {j.nice_to_have.length > 0 && <><h3 style={{ margin: "14px 0 8px" }}>Nice to have</h3><Chips items={j.nice_to_have} max={40} /></>}
          </section>
          {j.responsibilities.length > 0 && <section className="card"><header><h2>What you'll do</h2></header><ul className="clean">{j.responsibilities.map((r) => <li key={r}>{r}</li>)}</ul></section>}
          {j.qualifications.length > 0 && <section className="card"><header><h2>What they want</h2></header><ul className="clean">{j.qualifications.map((r) => <li key={r}>{r}</li>)}</ul></section>}
          {j.extractions?.[0] && <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>Extracted via {j.extractions[0].method}{j.extractions[0].model ? ` (${j.extractions[0].model})` : ""} in {j.extractions[0].latency_ms} ms{j.extractions[0].cost_usd ? ` · $${j.extractions[0].cost_usd.toFixed(4)}` : ""}{j.extractions[0].error ? ` · ${j.extractions[0].error}` : ""}</p>}
        </div>

        <aside className="stack">
          <section className="card">
            <header><h2>Pipeline</h2><StagePill stage={j.application.stage} /></header>
            <div className="stage-select" role="group" aria-label="Stage">
              {STAGES.map((s) => <button key={s} className="btn" aria-pressed={j.application.stage === s} onClick={() => j.application.stage !== s && run(() => api.setApplication(j.id, { stage: s as Stage }))}>{cap(s)}</button>)}
            </div>
            <label className="field" style={{ marginTop: 14 }}>Notes
              <textarea rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} onBlur={() => notes !== (j.application.notes ?? "") && run(() => api.setApplication(j.id, { notes }), "Saved")} placeholder="Recruiter, referral, questions to ask…" />
            </label>
            <label className="field" style={{ marginTop: 14 }}>Next step reminder (your local time)
              <input type="datetime-local" value={reminder} onChange={(event) => setReminder(event.target.value)} disabled={savingReminder} />
            </label>
            <div className="career-actions"><button className="btn" disabled={savingReminder || reminder === localDate(nextStep)} onClick={async () => {
              setSavingReminder(true);
              try { await run(() => api.setApplication(j.id, { next_step_at: reminder ? new Date(reminder).toISOString().slice(0, -1) : null }), reminder ? "Reminder saved" : "Reminder cleared"); }
              finally { setSavingReminder(false); }
            }}>{savingReminder ? "Saving…" : reminder ? "Save reminder" : "Clear reminder"}</button></div>
            {j.events && j.events.length > 0 && <ul className="timeline" style={{ margin: "16px 0 0", padding: 0 }}>{j.events.map((e) => <li key={e.id}><i /><span><b>{cap(e.to_stage)}</b> <span className="muted">· {ago(e.at)}</span></span></li>)}</ul>}
          </section>
          {m && (
            <section className="card">
              <header><h2>Why {m.score}?</h2></header>
              <div className="break">
                {(Object.keys(w) as (keyof typeof m.breakdown)[]).map((k) => (
                  <div className="bar" key={k}><span>{w[k]}</span><div className="track"><div className="fill" style={{ width: `${m.breakdown[k].score}%` }} /></div><span className="n">{m.breakdown[k].score}</span></div>
                ))}
              </div>
              {m.matched_skills.length > 0 && <><h3 style={{ margin: "16px 0 8px" }}>You have</h3><Chips items={m.matched_skills} kind="have" max={20} /></>}
              {m.missing_skills.length > 0 && <><h3 style={{ margin: "16px 0 8px" }}>Gaps</h3><Chips items={m.missing_skills} kind="miss" max={20} /></>}
              <p className="muted" style={{ fontSize: 12.5, marginBottom: 0 }}>Weights: skills 55 · level 15 · location 15 · pay 15. Tune them by editing your <a href="#/profile">profile</a>.</p>
            </section>
          )}
        </aside>
      </div>
    </>
  );
}
