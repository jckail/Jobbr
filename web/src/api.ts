import type { Config, Job, Profile, Stage, Stats } from "./types";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "") + "/api";
const TOKEN_KEY = "jobbr.token";

export const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) ?? ""; } catch { return ""; } };
export const setToken = (t: string) => { try { localStorage.setItem(TOKEN_KEY, t); } catch { /* private mode */ } };

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export const LOCKED_MESSAGE = "Editing is locked. Unlock it with the 🔒 control in the sidebar.";

/** Human-readable text for any thrown value; auth failures get a pointer to the unlock control. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError && e.status === 401) return LOCKED_MESSAGE;
  return e instanceof Error ? e.message : String(e);
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const t = getToken();
  if (t) headers["X-Jobbr-Token"] = t;
  const r = await fetch(BASE + path, { ...init, headers });
  if (!r.ok) {
    let msg = r.statusText;
    try { const b = await r.json(); msg = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail); } catch { /* */ }
    throw new ApiError(r.status, msg);
  }
  return r.status === 204 ? (undefined as T) : r.json();
}
const body = (m: string, b: unknown): RequestInit => ({ method: m, body: JSON.stringify(b) });

export const api = {
  config: () => req<Config>("/config"),
  jobs: (p: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams(Object.entries(p).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
    return req<Job[]>("/jobs?" + qs);
  },
  job: (id: number) => req<Job>(`/jobs/${id}`),
  addJob: (b: { url?: string; text?: string; company?: string; title?: string }) => req<Job>("/jobs", body("POST", b)),
  patchJob: (id: number, b: Partial<Pick<Job, "title" | "remote_policy" | "comp_min" | "comp_max" | "skills" | "summary">>) =>
    req<Job>(`/jobs/${id}`, body("PATCH", b)),
  reextract: (id: number) => req<Job>(`/jobs/${id}/reextract`, { method: "POST" }),
  deleteJob: (id: number) => req<void>(`/jobs/${id}`, { method: "DELETE" }),
  setApplication: (id: number, b: { stage?: Stage; notes?: string; next_step_at?: string | null; note?: string }) =>
    req<Job>(`/jobs/${id}/application`, body("PUT", b)),
  profile: () => req<Profile>("/profile"),
  saveProfile: (p: Partial<Profile>) => req<Profile>("/profile", body("PUT", p)),
  stats: () => req<Stats>("/stats"),
};
