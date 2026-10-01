import { api } from "../api";
import type { Stage } from "../types";
import { STAGES } from "../types";
import { Chips, Empty, Score, useAsync } from "../ui";
import { cap, money } from "../util";

function Bars({ rows }: { rows: { label: string; value: number; have?: boolean }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="bars">
      {rows.map((r) => (
        <div className="bar" key={r.label}>
          <span title={r.label} style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{r.label}</span>
          <div className="track" role="presentation"><div className={`fill ${r.have ? "have" : ""}`} style={{ width: `${(r.value / max) * 100}%` }} /></div>
          <span className="n">{r.value}</span>
        </div>
      ))}
    </div>
  );
}

function Spark({ data }: { data: { day: string; count: number }[] }) {
  const w = 420, h = 90, max = Math.max(1, ...data.map((d) => d.count)), bw = w / data.length;
  return (
    <svg viewBox={`0 0 ${w} ${h + 18}`} width="100%" role="img" aria-label="Jobs added per day, last 14 days">
      {data.map((d, i) => {
        const bh = (d.count / max) * h;
        return <g key={d.day}><rect x={i * bw + 3} y={h - bh} width={bw - 6} height={Math.max(bh, 2)} rx="3" fill={d.count ? "var(--accent)" : "var(--surface-2)"}><title>{`${d.day}: ${d.count}`}</title></rect>
          {i % 3 === 0 && <text x={i * bw + bw / 2} y={h + 14} textAnchor="middle" fontSize="10" fill="var(--muted)">{d.day.slice(5)}</text>}</g>;
      })}
    </svg>
  );
}

export default function Dashboard({ rev, onAdd, llm }: { rev: number; onAdd: () => void; llm?: boolean }) {
  const { data: s, loading, error } = useAsync(api.stats, [rev]);
  if (loading && !s) return <div className="skeleton" style={{ height: 320 }} />;
  if (error || !s) return <Empty title="Can't reach the API">{error?.message}</Empty>;
  const t = s.totals;
  if (t.jobs === 0)
    return (
      <>
        <div className="topbar"><div><h1>Welcome to Jobbr</h1><p>Paste a job link. Get structured data, a fit score, and a pipeline.</p></div></div>
        <Empty title="No jobs yet"><p>Add your first posting to see your market at a glance.</p><button className="btn primary" onClick={onAdd}>Add a job</button></Empty>
      </>
    );
  const active = STAGES.filter((x) => !["rejected", "withdrawn"].includes(x)) as Stage[];
  const gaps = s.skill_demand.filter((k) => !k.have).slice(0, 6).map((k) => k.skill);
  return (
    <>
      <div className="topbar">
        <div><h1>Overview</h1><p>Your search at a glance{llm ? "" : " — add an Anthropic key to unlock AI extraction"}.</p></div>
        <button className="btn primary" onClick={onAdd}>Add job</button>
      </div>
      <div className="kpis">
        <div className="card kpi"><h3>Tracked jobs</h3><div className="v">{t.jobs}</div><div className="s">{t.companies} companies</div></div>
        <div className="card kpi"><h3>Avg fit</h3><div className="v">{t.avg_score ?? "–"}</div><div className="s">out of 100</div></div>
        <div className="card kpi"><h3>Median comp</h3><div className="v">{money(t.median_comp)}</div><div className="s">where listed</div></div>
        <div className="card kpi"><h3>In flight</h3><div className="v">{s.stages.applied + s.stages.screen + s.stages.interview}</div><div className="s">{s.stages.offer} offer{s.stages.offer === 1 ? "" : "s"}</div></div>
        <div className="card kpi"><h3>AI spend</h3><div className="v">${t.ai_cost_usd.toFixed(2)}</div><div className="s">extraction cost</div></div>
      </div>
      <div className="grid2">
        <section className="card"><header><h2>Best matches</h2><a href="#/jobs">All jobs →</a></header>
          <div className="toplist">{s.top_matches.map((m) => (
            <a key={m.id} href={`#/jobs/${m.id}`}><Score value={m.score} size={40} /><div className="t"><div><b>{m.title}</b></div><div className="muted">{m.company}</div></div></a>
          ))}</div>
        </section>
        <section className="card"><header><h2>Pipeline</h2><a href="#/pipeline">Open board →</a></header>
          <Bars rows={active.map((st) => ({ label: cap(st), value: s.stages[st] }))} />
        </section>
      </div>
      <div className="grid2">
        <section className="card"><header><h2>Skills in demand</h2><span className="muted">green = you have it</span></header>
          <Bars rows={s.skill_demand.map((k) => ({ label: k.skill, value: k.jobs, have: k.have }))} />
          {gaps.length > 0 && <div style={{ marginTop: 14 }}><h3 style={{ marginBottom: 8 }}>Biggest gaps</h3><Chips items={gaps} kind="miss" /></div>}
        </section>
        <section className="card"><header><h2>Fit distribution</h2></header>
          <Bars rows={s.score_buckets.map((b) => ({ label: b.label, value: b.count }))} />
          <header style={{ marginTop: 22 }}><h2>Added, last 14 days</h2></header>
          <Spark data={s.added_per_day} />
        </section>
      </div>
    </>
  );
}
