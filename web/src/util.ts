export const money = (n: number | null | undefined, compact = true, currency = "USD") => {
  if (n == null) return "—";
  if (!/^[A-Z]{3}$/.test(currency)) return `${n.toLocaleString()} (currency not listed)`;
  const code = currency;
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: code, notation: compact ? "compact" : "standard", maximumFractionDigits: compact ? 1 : 0 }).format(n);
  } catch { return `${code} ${n.toLocaleString()}`; }
};

export const comp = (min: number | null, max: number | null, currency = "USD") =>
  min != null && max != null ? `${money(min, true, currency)} – ${money(max, true, currency)}` : min != null || max != null ? money(min ?? max, true, currency) : "Not listed";

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
