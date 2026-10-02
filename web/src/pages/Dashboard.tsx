import { api } from "../api";
import { BOARD_STAGES, type Job, type Profile } from "../types";
import { Chips, CompanyLogo, Empty, Icon, ICONS, Score, StagePill, useAsync } from "../ui";
import { cap, money, parseDate } from "../util";

function Bars({ rows }: { rows: { label: string; value: number; have?: boolean }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return <div className="bars">{rows.map((row) => <div className="bar" key={row.label}>
    <span title={row.label}>{row.label}</span><div className="track" aria-hidden="true"><div className={`fill ${row.have ? "have" : ""}`} style={{ width: `${row.value / max * 100}%` }} /></div><span className="n">{row.value}</span>
  </div>)}</div>;
}

function roleComp(job: Job): string {
  const currency = /^[A-Z]{3}$/.test(job.comp_currency) ? job.comp_currency : "USD";
  const format = (value: number) => {
    try { return new Intl.NumberFormat("en-US", { style: "currency", currency, notation: "compact", maximumFractionDigits: 1 }).format(value); }
    catch { return `${currency} ${value.toLocaleString()}`; }
  };
  if (job.comp_min == null && job.comp_max == null) return "Pay not listed";
  return job.comp_min != null && job.comp_max != null ? `${format(job.comp_min)} – ${format(job.comp_max)}` : format((job.comp_min ?? job.comp_max)!);
}

function MatchCard({ job }: { job: Job }) {
  const score = job.match?.score;
  return <article className="match-card">
    <div className="match-company"><CompanyLogo name={job.company.name} size={42} /><div><span>{job.company.name}</span><small>{cap(job.application.stage)}</small></div><div className="match-fit"><Score value={score} size={46} /><span>Profile fit</span></div></div>
    <h3><a href={`#/jobs/${job.id}`}>{job.title}</a></h3>
    <div className="match-facts"><span><Icon d={ICONS.pin} />{job.remote_policy === "remote" ? "Remote" : job.locations[0] || (job.remote_policy === "unknown" ? "Location not listed" : cap(job.remote_policy))}</span><span>{roleComp(job)}</span></div>
    <Chips items={job.skills} max={3} kind="accent" />
    <div className="match-bottom"><StagePill stage={job.application.stage} /><a className="btn compact" href={`#/jobs/${job.id}`}>View role<Icon d={ICONS.arrow} /></a></div>
  </article>;
}

function ProfileEssentials({ profile }: { profile?: Profile }) {
  if (!profile) return <section className="card profile-readiness"><h2>Your profile</h2><p className="muted">Add your experience and preferences to make role comparisons more useful.</p><a href="#/profile" className="text-link">Open profile<Icon d={ICONS.arrow} /></a></section>;
  const essentials = [
    { label: "Resume added", done: Boolean(profile.resume_text.trim()) },
    { label: "Target roles selected", done: profile.target_titles.length > 0 },
    { label: "Work preferences set", done: profile.remote_pref !== "unknown" || profile.locations.length > 0 },
    { label: "Salary preference set", done: profile.min_comp != null && profile.min_comp > 0 },
  ];
  const done = essentials.filter((item) => item.done).length;
  return <section className="card profile-readiness"><header><h2>Your profile</h2><span className="small-count">{done} of 4 essentials</span></header><div className="progress-track" role="progressbar" aria-label="Profile essentials complete" aria-valuenow={done} aria-valuemin={0} aria-valuemax={4}><span style={{ width: `${done * 25}%` }} /></div><ul className="profile-checklist">{essentials.map((item) => <li key={item.label} data-complete={item.done}><span className="check-marker">{item.done && <Icon d={ICONS.check} />}</span>{item.label}</li>)}</ul><a href="#/profile" className="text-link">{done === 4 ? "Review your profile" : "Complete your profile"}<Icon d={ICONS.arrow} /></a></section>;
}

export default function Dashboard({ rev, onAdd }: { rev: number; onAdd: () => void; llm?: boolean }) {
  const stats = useAsync(api.stats, [rev]);
  const jobs = useAsync(() => api.jobs({ sort: "score" }), [rev]);
  const profile = useAsync(api.profile, [rev]);
  const config = useAsync(api.config, [rev]);
  const s = stats.data;
  if (stats.loading && !s) return <div className="dashboard-loading" role="status" aria-label="Loading your overview"><div className="skeleton" style={{ height: 90 }} /><div className="skeleton" style={{ height: 160 }} /><div className="skeleton" style={{ height: 280 }} /></div>;
  if (stats.error || !s) return <Empty title="Your workspace couldn’t be loaded"><p>Check your connection and try again.</p><button className="btn primary" onClick={() => { stats.reload(); jobs.reload(); profile.reload(); }}>Try again</button></Empty>;
  const openJobs = (jobs.data ?? []).filter((job) => !["rejected", "withdrawn"].includes(job.application.stage));
  const best = openJobs.slice(0, 3);
  const strong = jobs.data ? openJobs.filter((job) => (job.match?.score ?? -1) >= 80).length : undefined;
  const gaps = s.skill_demand.filter((skill) => !skill.have);
  const activeApplications = s.stages.applied + s.stages.screen + s.stages.interview;
  const nextStep = openJobs.filter((job) => job.application.next_step_at && Number.isFinite(parseDate(job.application.next_step_at).getTime())).sort((a, b) => parseDate(a.application.next_step_at!).getTime() - parseDate(b.application.next_step_at!).getTime())[0];
  const firstSaved = openJobs.find((job) => job.application.stage === "saved");
  const prepare = openJobs.find((job) => ["interview", "screen"].includes(job.application.stage));
  const demo = config.data && "seed_demo" in config.data && config.data.seed_demo === true;
  const firstName = profile.data?.name.trim().split(/\s+/)[0];
  return <>
    <div className="overview-heading"><div><h1>{firstName ? `Your next chapter, ${firstName}.` : "Your next chapter starts here."}</h1><p>A clear plan for your next move.</p></div><span className="workspace-status"><span />{demo ? "Demo workspace" : "Your job search"}</span></div>
    {demo && <div className="demo-notice"><Icon d={ICONS.book} /><span>This workspace includes seeded examples. Use your own resume and postings for meaningful fit scores.</span></div>}
    {s.totals.jobs === 0 ? <div className="welcome-grid"><section className="plan-card welcome-card"><div className="plan-icon"><Icon d={ICONS.target} /></div><h2>One place for your next move.</h2><p>Turn a job posting into a clear picture of the role, your fit, and what to do next.</p><button className="btn primary" onClick={onAdd}><Icon d={ICONS.plus} />Add your first job</button><div className="welcome-steps"><span><Icon d={ICONS.link} />Save a posting</span><span><Icon d={ICONS.target} />Understand your fit</span><span><Icon d={ICONS.board} />Track your progress</span></div></section><ProfileEssentials profile={profile.data} /></div>
      : <div className="command-grid"><div className="command-main">
        <section className="plan-card"><div className="plan-copy"><span className="plan-label"><Icon d={ICONS.sparkles} />A little focus goes a long way</span><h2>Make your next move count.</h2><p>{firstSaved ? `Start with ${firstSaved.company.name}. Review the role’s fit and requirements before you apply.` : "Review your strongest opportunities and keep the next step moving."}</p><a href={firstSaved ? `#/jobs/${firstSaved.id}` : "#/jobs"} className="btn primary">{firstSaved ? "Review your next opportunity" : "Explore your jobs"}<Icon d={ICONS.arrow} /></a></div><div className="plan-illustration" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="plan-symbol"><Icon d={ICONS.target} /></div><span className="orbit-dot dot-one" /><span className="orbit-dot dot-two" /></div></section>
        <div className="overview-metrics">
          <div className="metric"><span className="metric-icon"><Icon d={ICONS.jobs} /></span><span className="metric-label">Tracked jobs</span><strong>{s.totals.jobs}</strong><small>{s.totals.companies} companies</small></div>
          <div className="metric"><span className="metric-icon green"><Icon d={ICONS.target} /></span><span className="metric-label">Strong matches</span><strong>{strong ?? "—"}</strong><small>Open roles with fit 80+</small></div>
          <div className="metric"><span className="metric-icon blue"><Icon d={ICONS.board} /></span><span className="metric-label">In progress</span><strong>{activeApplications}</strong><small>{s.stages.offer} offer{s.stages.offer === 1 ? "" : "s"} received</small></div>
          <div className="metric"><span className="metric-icon amber"><span aria-hidden="true">$</span></span><span className="metric-label">Median salary</span><strong>{money(s.totals.median_comp)}</strong><small>USD · where ranges are listed</small></div>
        </div>
        <section className="matches-section"><header className="section-heading"><div><h2>Opportunities worth a closer look</h2><p>Ranked by your profile and preferences.</p></div><a className="text-link" href="#/jobs">All jobs<Icon d={ICONS.arrow} /></a></header>
          {jobs.loading && !jobs.data ? <div className="skeleton" style={{ height: 180 }} /> : jobs.error ? <div className="card inline-empty"><p>Role details couldn’t be loaded.</p><button className="btn" onClick={jobs.reload}>Try again</button></div> : best.length ? <div className="match-grid">{best.map((job) => <MatchCard job={job} key={job.id} />)}</div> : <div className="card inline-empty"><h3>Room for your next opportunity</h3><p>Your tracked roles are closed. Add a new posting to explore your next match.</p><button className="btn" onClick={onAdd}>Add job</button></div>}
        </section>
        <section className="card pipeline-summary"><header><div><h2>Keep your search moving</h2><p className="muted">Every opportunity has a next step.</p></div><a className="text-link" href="#/pipeline">Open pipeline<Icon d={ICONS.arrow} /></a></header><div className="pipeline-stages">{BOARD_STAGES.map((stage) => <a href="#/pipeline" key={stage} className={`pipeline-stage stage-${stage}`}><span className="stage-label"><i />{cap(stage)}</span><strong>{s.stages[stage]}</strong><span className="pipeline-track"><span style={{ width: `${s.stages[stage] / Math.max(1, s.totals.jobs) * 100}%` }} /></span></a>)}</div></section>
        <details className="search-insights"><summary><Icon d={ICONS.dash} /><span>Understand your search</span><Icon d={ICONS.chevron} /></summary><div className="insights-grid"><section><h2>Skills across your saved jobs</h2><p className="muted small">Green means detected in your profile. Counts are postings.</p><Bars rows={s.skill_demand.map((skill) => ({ label: skill.skill, value: skill.jobs, have: skill.have }))} /></section><section><h2>Profile fit distribution</h2><p className="muted small">Average fit: {s.totals.avg_score ?? "not scored"}{s.totals.avg_score != null && " out of 100"}.</p><Bars rows={s.score_buckets.map((bucket) => ({ label: bucket.label, value: bucket.count }))} /></section></div></details>
      </div><aside className="command-rail" aria-label="Your next actions">
        <section className="card focus-card"><header><h2>Your focus today</h2><Icon d={ICONS.target} /></header><div className="focus-actions">
          {nextStep && <a className="focus-action" href={`#/jobs/${nextStep.id}`}><span className="focus-icon blue"><Icon d={ICONS.clock} /></span><span><b>Your next step at {nextStep.company.name}</b><small>{parseDate(nextStep.application.next_step_at!).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</small></span><Icon d={ICONS.chevron} /></a>}
          <a className="focus-action" href={firstSaved ? `#/jobs/${firstSaved.id}` : "#/jobs"}><span className="focus-icon green"><Icon d={ICONS.jobs} /></span><span><b>{firstSaved ? "Review a saved opportunity" : "Explore your opportunities"}</b><small>{firstSaved ? `${firstSaved.title} at ${firstSaved.company.name}` : "Compare requirements and your profile fit."}</small></span><Icon d={ICONS.chevron} /></a>
          <a className="focus-action" href="#/profile"><span className="focus-icon"><Icon d={ICONS.user} /></span><span><b>Make your experience count</b><small>Add supported experience and target preferences.</small></span><Icon d={ICONS.chevron} /></a>
          {prepare && <a className="focus-action" href={`#/jobs/${prepare.id}`}><span className="focus-icon amber"><Icon d={ICONS.book} /></span><span><b>Prepare for {prepare.company.name}</b><small>Review the role and gather relevant examples.</small></span><Icon d={ICONS.chevron} /></a>}
        </div></section>
        <section className="card coach-card"><span className="coach-label"><Icon d={ICONS.sparkles} />Career compass</span><h2>Close the gaps that matter.</h2><p className="muted">A useful next step, grounded in your saved roles.</p><div className="coach-insights">{gaps.length ? gaps.slice(0, 2).map((gap) => <div key={gap.skill}><span className="coach-bullet" /><p><b>{gap.skill}</b> appears in {gap.jobs} saved posting{gap.jobs === 1 ? "" : "s"}, but isn’t detected in your resume. Add relevant experience if you have it, or consider building it.</p></div>) : <div><span className="coach-bullet" /><p>{profile.data?.resume_text.trim() ? "Your detected skills cover the most common requirements in these postings. Review each role’s details for the full picture." : "Add your resume to see which requirements your experience already covers."}</p></div>}</div><a href="#/profile" className="btn primary">Improve your profile<Icon d={ICONS.arrow} /></a><p className="fit-note"><Icon d={ICONS.target} />Fit reflects skill overlap and preferences. It isn’t a hiring prediction.</p></section>
        <ProfileEssentials profile={profile.data} />
      </aside></div>}
    <div className="overview-footer"><span>Small steps. Better decisions. Your next chapter.</span><a href="#/profile">Your profile shapes your matches<Icon d={ICONS.arrow} /></a></div>
  </>;
}
