import { useEffect, useState } from "react";
import { api } from "../api";
import { STAGES, type Stage } from "../types";
import { Chips, CompanyLogo, Empty, Icon, ICONS, Score, StagePill, useAsync, useToast } from "../ui";
import { ago, cap, comp } from "../util";

export default function JobDetail({ id, rev, onChange }: { id: number; rev: number; onChange: () => void }) {
  const { data: j, loading, error, reload } = useAsync(() => api.job(id), [id, rev]);
  const [notes, setNotes] = useState("");
  const toast = useToast();
  useEffect(() => { if (j) setNotes(j.application.notes ?? ""); }, [j?.id, j?.application.notes]);

  if (loading && !j) return <div className="skeleton" style={{ height: 360 }} />;
  if (error || !j) return <Empty title="Job not found"><a href="#/jobs">Back to jobs</a></Empty>;

  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    try { await fn(); if (ok) toast(ok); onChange(); reload(); }
    catch (e) { toast((e as { status?: number }).status === 401 ? "Editing is locked — enter the access token in the sidebar." : (e as Error).message, true); }
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
