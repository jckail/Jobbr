import { useEffect, useState } from "react";
import { api } from "../api";
import type { Profile } from "../types";
import { Chips, useAsync, useGuarded } from "../ui";
import { cap } from "../util";

const SENIORITY = ["unknown", "intern", "junior", "mid", "senior", "staff", "principal"];

export default function ProfilePage({ onChange }: { onChange: () => void }) {
  const { data } = useAsync(api.profile, []);
  const [p, setP] = useState<Profile | null>(null);
  const [busy, setBusy] = useState(false);
  const guarded = useGuarded();
  useEffect(() => { if (data) setP(data); }, [data]);
  if (!p) return <div className="skeleton" style={{ height: 320 }} />;
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setP({ ...p, [k]: v });
  const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

  async function save() {
    setBusy(true);
    const { skills: _derived, ...rest } = p!; // skills are re-derived from the resume server-side
    let saved: Profile | undefined;
    const ok = await guarded(async () => { saved = await api.saveProfile(rest); },
      "Saved · every job re-scored");
    if (ok && saved) { setP(saved); onChange(); }
    setBusy(false);
  }

  return (
    <>
      <div className="topbar"><div><h1>Your profile</h1><p>Every job is scored against this. Saving re-scores everything instantly.</p></div><button className="btn primary" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save & re-score"}</button></div>
      <div className="profile">
        <section className="card form">
          <div className="two">
            <label className="field">Name<input type="text" value={p.name} onChange={(e) => set("name", e.target.value)} /></label>
            <label className="field">Headline<input type="text" value={p.headline ?? ""} onChange={(e) => set("headline", e.target.value)} placeholder="Data & AI engineer" /></label>
          </div>
          <label className="field">Resume <small>Paste plain text — skills are detected automatically</small>
            <textarea rows={14} value={p.resume_text} onChange={(e) => set("resume_text", e.target.value)} />
          </label>
        </section>
        <section className="card form">
          <h2>Preferences</h2>
          <div className="two">
            <label className="field">Level<select value={p.seniority} onChange={(e) => set("seniority", e.target.value)}>{SENIORITY.map((s) => <option key={s} value={s}>{cap(s)}</option>)}</select></label>
            <label className="field">Years of experience<input type="number" min={0} value={p.years_experience ?? ""} onChange={(e) => set("years_experience", e.target.value ? +e.target.value : null)} /></label>
          </div>
          <div className="two">
            <label className="field">Work style<select value={p.remote_pref} onChange={(e) => set("remote_pref", e.target.value as Profile["remote_pref"])}><option value="unknown">No preference</option><option value="remote">Remote</option><option value="hybrid">Hybrid</option><option value="onsite">On-site</option></select></label>
            <label className="field">Minimum pay (USD)<input type="number" step={5000} min={0} value={p.min_comp ?? ""} onChange={(e) => set("min_comp", e.target.value ? +e.target.value : null)} /></label>
          </div>
          <label className="field">Locations <small>comma separated</small><input type="text" value={p.locations.join(", ")} onChange={(e) => set("locations", list(e.target.value))} placeholder="Seattle, WA, New York, NY" /></label>
          <label className="field">Target titles <small>comma separated</small><input type="text" value={p.target_titles.join(", ")} onChange={(e) => set("target_titles", list(e.target.value))} /></label>
          <div><h3 style={{ marginBottom: 8 }}>Detected skills ({p.skills.length})</h3>{p.skills.length ? <Chips items={p.skills} kind="have" max={60} /> : <span className="muted">Save to detect skills from your resume.</span>}</div>
        </section>
      </div>
    </>
  );
}
