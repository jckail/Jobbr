import { useEffect, useState } from "react";
import { api } from "../api";
import { Chips, CompanyLogo, Empty, Score, StagePill, useAsync } from "../ui";
import { ago, cap, comp } from "../util";

export default function Jobs({ rev, onAdd }: { rev: number; onAdd: () => void }) {
  const [q, setQ] = useState(""), [dq, setDq] = useState("");
  const [stage, setStage] = useState(""), [remote, setRemote] = useState(""), [sort, setSort] = useState("score"), [min, setMin] = useState(0);
  useEffect(() => { const t = setTimeout(() => setDq(q), 200); return () => clearTimeout(t); }, [q]);
  const { data, loading } = useAsync(() => api.jobs({ q: dq, stage, remote, sort, min_score: min }), [dq, stage, remote, sort, min, rev]);

  return (
    <>
      <div className="topbar"><div><h1>Jobs</h1><p>{data ? `${data.length} result${data.length === 1 ? "" : "s"}` : " "}</p></div><button className="btn primary" onClick={onAdd}>Add job</button></div>
      <div className="filters">
        <input type="search" placeholder="Search title, company or skill…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search" />
        <select value={stage} onChange={(e) => setStage(e.target.value)} aria-label="Stage"><option value="">Any stage</option>{["saved", "applied", "screen", "interview", "offer", "rejected", "withdrawn"].map((s) => <option key={s} value={s}>{cap(s)}</option>)}</select>
        <select value={remote} onChange={(e) => setRemote(e.target.value)} aria-label="Work style"><option value="">Any work style</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="onsite">On-site</option></select>
        <select value={min} onChange={(e) => setMin(+e.target.value)} aria-label="Minimum score"><option value={0}>Any fit</option><option value={60}>Fit 60+</option><option value={75}>Fit 75+</option><option value={85}>Fit 85+</option></select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort"><option value="score">Best fit</option><option value="recent">Newest</option><option value="comp">Highest pay</option></select>
      </div>
      {loading && !data ? <div className="skeleton" style={{ height: 240 }} /> : !data?.length ? (
        <Empty title="Nothing matches"><p>Try clearing filters, or add a new posting.</p><button className="btn primary" onClick={onAdd}>Add job</button></Empty>
      ) : (
        <div className="jobs">
          {data.map((j) => (
            <a key={j.id} className="card job" href={`#/jobs/${j.id}`}>
              <CompanyLogo name={j.company.name} />
              <div style={{ minWidth: 0 }}>
                <h2>{j.title}</h2>
                <div className="meta"><span>{j.company.name}</span><span>{j.remote_policy !== "unknown" ? cap(j.remote_policy) : ""}</span><span>{j.locations[0] ?? ""}</span><span>{comp(j.comp_min, j.comp_max)}</span><span>{ago(j.first_seen_at)}</span></div>
                <Chips items={j.skills} kind="accent" max={6} />
              </div>
              <div className="right"><Score value={j.match?.score} /><StagePill stage={j.application.stage} /></div>
            </a>
          ))}
        </div>
      )}
    </>
  );
}
