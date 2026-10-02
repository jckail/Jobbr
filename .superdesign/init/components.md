# Shared primitives
React 18 + TypeScript, custom CSS. Icon, Score, CompanyLogo, StagePill, Chips, Empty, Modal and ToastProvider.

## `web/src/ui.tsx`
```tsx
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { errorMessage } from "./api";
import { cap, hue, initials, scoreTone } from "./util";

export const Icon = ({ d, ...p }: { d: string } & React.SVGProps<SVGSVGElement>) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden {...p}>
    {d.split("|").map((x, i) => <path key={i} d={x} />)}
  </svg>
);
export const ICONS = {
  dash: "M4 13h6V4H4z|M14 20h6V4h-6z|M4 20h6v-3H4z",
  jobs: "M3 7h18v12H3z|M9 7V5h6v2",
  board: "M4 4h5v16H4z|M10 4h5v10h-5z|M16 4h4v6h-4z",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z|M4 20c0-4 4-6 8-6s8 2 8 6",
  plus: "M12 5v14|M5 12h14",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1|M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7|M20 4v7h-7",
  trash: "M4 7h16|M10 11v6|M14 11v6|M6 7l1 13h10l1-13|M9 7V4h6v3",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z|M12 2v2|M12 20v2|M4.9 4.9l1.4 1.4|M17.7 17.7l1.4 1.4|M2 12h2|M20 12h2|M4.9 19.1l1.4-1.4|M17.7 6.3l1.4-1.4",
  ext: "M14 4h6v6|M20 4l-9 9|M18 14v5H5V6h5",
};

export function Score({ value, size = 52 }: { value: number | null | undefined; size?: number }) {
  const tone = scoreTone(value), r = size / 2 - 4, c = 2 * Math.PI * r;
  return (
    <div className="score" data-tone={tone} style={{ width: size, height: size, fontSize: size * 0.3 }}
      role="img" aria-label={value == null ? "No match score" : `Match score ${value} out of 100`}>
      <svg viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-2)" strokeWidth="4" />
        {value != null && <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--c)" strokeWidth="4" strokeLinecap="round"
          strokeDasharray={`${(c * value) / 100} ${c}`} style={{ transition: "stroke-dasharray .5s" }} />}
      </svg>
      <b>{value ?? "–"}</b>
    </div>
  );
}

export const CompanyLogo = ({ name, size = 38 }: { name: string; size?: number }) => (
  <div className="logo-co" aria-hidden style={{ width: size, height: size, background: `hsl(${hue(name)} 55% 46%)` }}>{initials(name)}</div>
);

export const StagePill = ({ stage }: { stage: string }) => {
  const tone = { offer: "great", interview: "good", screen: "good", applied: "fair", rejected: "low", withdrawn: "none", saved: "none" }[stage] ?? "none";
  return <span className="pill" data-tone={tone}>{cap(stage)}</span>;
};

export const Chips = ({ items, kind, max = 8 }: { items: string[]; kind?: "have" | "miss" | "accent"; max?: number }) => (
  <div className="chips">
    {items.slice(0, max).map((s) => <span key={s} className={`chip ${kind ?? ""}`}>{s}</span>)}
    {items.length > max && <span className="chip">+{items.length - max}</span>}
  </div>
);

export const Empty = ({ title, children }: { title: string; children?: ReactNode }) => (
  <div className="card empty"><h2>{title}</h2><div>{children}</div></div>
);

export function Modal({ onClose, title, children }: { onClose: () => void; title: string; children: ReactNode }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="card modal" role="dialog" aria-modal aria-label={title}><header><h2>{title}</h2></header>{children}</div>
    </div>
  );
}

// toast
const ToastCtx = createContext<(msg: string, err?: boolean) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [t, setT] = useState<{ msg: string; err: boolean } | null>(null);
  const show = useCallback((msg: string, err = false) => { setT({ msg, err }); setTimeout(() => setT(null), 4200); }, []);
  return <ToastCtx.Provider value={show}>{children}{t && <div className={`toast ${t.err ? "err" : ""}`} role="status">{t.msg}</div>}</ToastCtx.Provider>;
}

/** Run an async action; toast `ok` on success or the error message on failure. Resolves to success. */
export function useGuarded() {
  const toast = useToast();
  return useCallback(async (fn: () => Promise<unknown>, ok?: string): Promise<boolean> => {
    try {
      await fn();
      if (ok) toast(ok);
      return true;
    } catch (e) {
      toast(errorMessage(e), true);
      return false;
    }
  }, [toast]);
}

// tiny data hook
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [state, set] = useState<{ data?: T; error?: Error; loading: boolean }>({ loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    set((s) => ({ ...s, loading: true }));
    fn().then((data) => live && set({ data, loading: false })).catch((error) => live && set({ error, loading: false }));
    return () => { live = false; };
    // `fn` is intentionally excluded: callers re-run it via `deps`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...state, reload: () => setTick((x) => x + 1) };
}

// hash router: works under any mount path, no server rewrites needed
export function useRoute(): [string, (to: string) => void] {
  const get = () => window.location.hash.replace(/^#/, "") || "/";
  const [r, set] = useState(get);
  useEffect(() => { const h = () => set(get()); window.addEventListener("hashchange", h); return () => window.removeEventListener("hashchange", h); }, []);
  return [r, (to) => { window.location.hash = to; }];
}

```

## `web/src/util.ts`
```ts
export const money = (n: number | null | undefined, compact = true) =>
  n == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: compact ? "compact" : "standard", maximumFractionDigits: compact ? 1 : 0 }).format(n);

export const comp = (min: number | null, max: number | null) =>
  min && max ? `${money(min)} – ${money(max)}` : min || max ? money(min ?? max) : "Not listed";

// The API stores naive UTC timestamps.
export const parseDate = (s: string) => new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : s + "Z");

export function ago(s: string): string {
  const d = (Date.now() - parseDate(s).getTime()) / 1000;
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  if (d < 86400 * 30) return `${Math.floor(d / 86400)}d ago`;
  return parseDate(s).toLocaleDateString();
}

export const scoreTone = (s: number | null | undefined) => (s == null ? "none" : s >= 80 ? "great" : s >= 60 ? "good" : s >= 40 ? "fair" : "low");
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
export const initials = (s: string) => s.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
export const hue = (s: string) => [...s].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);

```
