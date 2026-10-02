export const DESTINATIONS = Object.freeze({
  local: "http://localhost:8000/jobbr",
  production: "https://jckail.com/jobbr",
});
export const MAX_TEXT_LENGTH = 60000;

export function destination(key) {
  if (!Object.hasOwn(DESTINATIONS, key)) throw new Error("Choose a supported Jobbr destination.");
  return DESTINATIONS[key];
}

export function postingUrl(value) {
  let url;
  try { url = new URL(value); } catch { throw new Error("Enter a valid posting URL."); }
  if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) {
    throw new Error("Use an HTTP or HTTPS posting URL without embedded credentials.");
  }
  url.hash = "";
  return url.href;
}

export function jobPayload(url, text) {
  const payload = { url: postingUrl(url) };
  const cleanText = text.trim();
  if (cleanText.length > MAX_TEXT_LENGTH) throw new Error("Trim the posting to 60,000 characters before saving.");
  if (cleanText) payload.text = cleanText;
  return payload;
}

export async function apiRequest(base, path, { token = "", payload, fetcher = fetch } = {}) {
  if (!Object.values(DESTINATIONS).includes(base)) throw new Error("Unsupported Jobbr destination.");
  if (!["/config", "/jobs"].includes(path)) throw new Error("Unsupported Jobbr request.");
  const headers = { Accept: "application/json" };
  if (payload) headers["Content-Type"] = "application/json";
  if (token) headers["X-Jobbr-Token"] = token;
  const response = await fetcher(base + "/api" + path, {
    method: payload ? "POST" : "GET", headers,
    ...(payload ? { body: JSON.stringify(payload) } : {}),
    credentials: "omit", redirect: "error", cache: "no-store",
    signal: AbortSignal.timeout(90000),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error("Editing is locked. Enter the API token for this destination and try again.");
    let detail = `Jobbr returned HTTP ${response.status}.`;
    try { const body = await response.json(); if (typeof body.detail === "string") detail = body.detail; } catch { /* non-JSON proxy errors */ }
    throw new Error(detail);
  }
  return response.json();
}
