import { useEffect, useRef, useState } from "react";
import { api, errorMessage, getToken } from "../api";
import type { AvailabilityObservation, Config } from "../types";
import { parseDate } from "../util";

const labels = { available: "Listed when checked", unavailable: "Not listed when checked", unknown: "Availability unknown" };
const reasons: Record<AvailabilityObservation["reason"], string> = {
  listed: "The posting appeared in the checked board snapshot. Availability can change afterward.",
  absent_complete_board: "The posting did not appear in a complete board snapshot. Review the source for its current status.",
  incomplete_snapshot: "The board snapshot was incomplete. Absence from that snapshot cannot establish availability.",
  upstream_unavailable: "The source could not be checked. Try checking again later.",
  invalid_data: "The source returned invalid posting data. Try checking again later.",
  unsupported_identity: "This posting has no supported Greenhouse or Lever identity. Review its original posting.",
};

export default function AvailabilityPanel({ jobId, config }: { jobId: number; config?: Config }) {
  const [observation, setObservation] = useState<AvailabilityObservation | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const running = useRef(false);
  const mounted = useRef(true);
  const allowed = !!config && (config.auth_enabled || (config.write_protected && !!getToken()));
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const check = async () => {
    if (running.current || !allowed) return;
    running.current = true; setChecking(true); setError("");
    try {
      const result = await api.checkAvailability(jobId);
      if (mounted.current) setObservation(result);
    } catch (failure) { if (mounted.current) setError(errorMessage(failure)); }
    finally { running.current = false; if (mounted.current) setChecking(false); }
  };
  return <section className="card stack" aria-busy={checking}>
    <header><h2>Posting availability</h2></header>
    <p className="muted">Choose Check availability to read a supported career board. This check uses no AI and does not change your tracked job or application stage. Its result is kept only on this page.</p>
    {!allowed && <p>Protected access is required to check availability. Open Access to sign in or enter the instance token.</p>}
    <button className="btn" disabled={checking || !allowed} onClick={() => void check()}>{checking ? "Checking availability…" : error ? "Retry availability check" : observation ? "Check availability again" : "Check availability"}</button>
    {checking && <p role="status">Checking the source board…</p>}
    {error && <p role="alert">{error} {observation && "The earlier observation below has not been refreshed."}</p>}
    {observation && allowed && <div role="status">
      <h3>{labels[observation.state]}</h3>
      <p>Checked <time dateTime={observation.checked_at}>{parseDate(observation.checked_at).toLocaleString(undefined, { timeZoneName: "short" })}</time>.</p>
      <p className="muted">{reasons[observation.reason]}</p>
      {observation.source_url && <a href={observation.source_url} target="_blank" rel="noopener noreferrer">Review checked source</a>}
    </div>}
  </section>;
}
