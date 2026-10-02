import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
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
  search: "M21 21l-5-5|M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13z",
  arrow: "M5 12h14|M13 6l6 6-6 6",
  chevron: "M9 6l6 6-6 6",
  check: "M5 12l4 4L19 6",
  close: "M6 6l12 12|M18 6L6 18",
  target: "M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16z|M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z|M12 11v2",
  sparkles: "M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z|M21 2v4|M19 4h4",
  clock: "M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16z|M12 7v5l3 2",
  pin: "M12 22s7-7 7-13a7 7 0 0 0-14 0c0 6 7 13 7 13z|M12 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  book: "M3 4h7l2 2 2-2h7v15h-7l-2 2-2-2H3z|M12 6v15",
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
  const dialog = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  const titleId = useId();
  useEffect(() => { close.current = onClose; }, [onClose]);
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () => Array.from(dialog.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex="0"]') ?? []).filter((element) => element.getClientRects().length > 0);
    const initial = dialog.current?.querySelector<HTMLElement>("[autofocus], input, textarea") ?? focusable()[0];
    (initial ?? dialog.current)?.focus();
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); close.current(); }
      if (event.key !== "Tab") return;
      const elements = focusable(), first = elements[0], last = elements[elements.length - 1];
      if (!first) { event.preventDefault(); dialog.current?.focus(); }
      else if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", keyboard);
    return () => { document.removeEventListener("keydown", keyboard); document.body.style.overflow = previousOverflow; previous?.focus(); };
  }, []);
  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="card modal" ref={dialog} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
        <header><h2 id={titleId}>{title}</h2><button type="button" className="icon-button" onClick={onClose} aria-label={`Close ${title}`}><Icon d={ICONS.close} /></button></header>{children}
      </div>
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
