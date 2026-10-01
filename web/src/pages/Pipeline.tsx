import { useState } from "react";
import { api } from "../api";
import { BOARD_STAGES, type Job, type Stage } from "../types";
import { Empty, Score, StagePill, useAsync, useGuarded } from "../ui";
import { ago, cap, comp } from "../util";

export default function Pipeline({ rev, onChange }: { rev: number; onChange: () => void }) {
  const { data, loading, reload } = useAsync(() => api.jobs({ sort: "score" }), [rev]);
  const [over, setOver] = useState<Stage | null>(null);
  const [dragId, setDragId] = useState<number | null>(null);
  const guarded = useGuarded();
  if (loading && !data) return <div className="skeleton" style={{ height: 320 }} />;
  const jobs = data ?? [];
  if (!jobs.length) return <Empty title="Your pipeline is empty">Add a job to start tracking it.</Empty>;

  async function move(id: number, stage: Stage) {
    const j = jobs.find((x) => x.id === id);
    if (!j || j.application.stage === stage) return;
    if (await guarded(() => api.setApplication(id, { stage }))) { onChange(); reload(); }
  }
  const card = (j: Job) => (
    <a key={j.id} href={`#/jobs/${j.id}`} className={`kcard ${dragId === j.id ? "drag" : ""}`} draggable
      onDragStart={(e) => { setDragId(j.id); e.dataTransfer.setData("text/plain", String(j.id)); e.dataTransfer.effectAllowed = "move"; }}
      onDragEnd={() => { setDragId(null); setOver(null); }}>
      <div className="row"><div style={{ minWidth: 0 }}><b>{j.title}</b><div className="muted" style={{ fontSize: 13 }}>{j.company.name}</div></div><Score value={j.match?.score} size={40} /></div>
      <div className="muted" style={{ fontSize: 12.5 }}>{comp(j.comp_min, j.comp_max)} · {ago(j.first_seen_at)}</div>
    </a>
  );
  const closed = jobs.filter((j) => ["rejected", "withdrawn"].includes(j.application.stage));
  return (
    <>
      <div className="topbar"><div><h1>Pipeline</h1><p>Drag a card to change its stage.</p></div></div>
      <div className="board">
        {BOARD_STAGES.map((st) => {
          const items = jobs.filter((j) => j.application.stage === st);
          return (
            <section key={st} className={`col ${over === st ? "over" : ""}`} aria-label={cap(st)}
              onDragOver={(e) => { e.preventDefault(); setOver(st); }} onDragLeave={() => setOver((o) => (o === st ? null : o))}
              onDrop={(e) => { e.preventDefault(); setOver(null); move(Number(e.dataTransfer.getData("text/plain")), st); }}>
              <h3><span>{cap(st)}</span><span>{items.length}</span></h3>
              {items.map(card)}
            </section>
          );
        })}
      </div>
      {closed.length > 0 && (
        <section className="card closed"><header><h2>Closed</h2></header>
          <div className="toplist">{closed.map((j) => (
            <a key={j.id} href={`#/jobs/${j.id}`}><Score value={j.match?.score} size={36} /><div className="t"><div><b>{j.title}</b></div><div className="muted">{j.company.name}</div></div><StagePill stage={j.application.stage} /></a>
          ))}</div>
        </section>
      )}
    </>
  );
}
