import type { AuthSession, CareerKind, CareerResult, Config, DiscoveryProvider, DiscoverySnapshot, Job, Profile, ResumePreview, Stage, Stats } from "./types";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "") + "/api";
const TOKEN_KEY = "jobbr.token";

// Delete legacy persistent credentials; access tokens now expire with this tab's session.
export const getToken = () => {
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* unavailable storage */ }
  try { return sessionStorage.getItem(TOKEN_KEY) ?? ""; } catch { return ""; }
};
export const setToken = (token: string) => {
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* unavailable storage */ }
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch { /* unavailable storage */ }
};
let csrfToken = "";
export const clearSession = () => { csrfToken = ""; };

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export const LOCKED_MESSAGE = "Access is locked. Open Access to sign in or enter the instance token.";

/** Human-readable text for any thrown value; auth failures get a pointer to the unlock control. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError && e.status === 401) return LOCKED_MESSAGE;
  return e instanceof Error ? e.message : String(e);
}

async function req<T>(path: string, init: RequestInit = {}, notifyAuthFailure = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("X-Jobbr-Token", token);
  const method = (init.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD"].includes(method) && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  const r = await fetch(BASE + path, { ...init, credentials: "same-origin", headers });
  if (!r.ok) {
    let msg = r.statusText;
    try { const b = await r.json(); msg = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail); } catch { /* non-JSON server error */ }
    if (notifyAuthFailure && r.status === 401 && !path.startsWith("/auth/") && path !== "/config") {
      clearSession();
      window.dispatchEvent(new Event("jobbr:access-expired"));
    }
    throw new ApiError(r.status, msg);
  }
  return r.status === 204 ? (undefined as T) : r.json();
}
const body = (m: string, b: unknown): RequestInit => ({ method: m, body: JSON.stringify(b) });

export const api = {
  session: async () => {
    const session = await req<AuthSession>("/auth/session");
    csrfToken = session.authenticated ? session.csrf_token ?? "" : "";
    return session;
  },
  logout: async () => { await req<void>("/auth/logout", { method: "POST" }); clearSession(); },
  career: (id: number, kind: CareerKind, signal?: AbortSignal) =>
    req<CareerResult>(`/jobs/${id}/career/${kind}`, { method: "POST", signal }),
  previewResume: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return req<ResumePreview>("/profile/resume", { method: "POST", body: form });
  },
  discover: (provider: DiscoveryProvider, board: string, q = "", remote = "") => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (remote) params.set("remote", remote);
    return req<DiscoverySnapshot>(`/discovery/boards/${encodeURIComponent(provider)}/${encodeURIComponent(board)}?${params}`);
  },
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
  validateToken: () => req<Profile>("/profile", {}, false),
  profile: () => req<Profile>("/profile"),
  saveProfile: (p: Partial<Profile>) => req<Profile>("/profile", body("PUT", p)),
  stats: () => req<Stats>("/stats"),
};
