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

export function aiSelection(config) {
  if (!config || !["openai", "anthropic"].includes(config.ai_provider)
    || typeof config.ai_model !== "string" || !config.ai_model.trim() || config.ai_model.length > 200
    || typeof config.llm_enabled !== "boolean" || typeof config.auth_enabled !== "boolean") {
    throw new Error("Could not verify extraction settings. Check Jobbr before saving.");
  }
  return {
    "X-Jobbr-AI-Provider": config.ai_provider,
    "X-Jobbr-AI-Model": config.ai_model,
    "X-Jobbr-AI-Enabled": String(config.llm_enabled),
  };
}

export function aiDisclosure(config) {
  aiSelection(config);
  const provider = config.ai_provider === "anthropic" ? "Anthropic Claude" : "OpenAI";
  return `Saving sends posting text to ${provider} (${config.ai_model}) for extraction and may incur API charges. If you send only a URL, Jobbr fetches its posting text first. Dollar cost is not estimated. Your resume is not included. Continue?`;
}

export async function savePosting(base, { token = "", payload, fetcher = fetch, confirmAI } = {}) {
  const config = await apiRequest(base, "/config", { fetcher });
  const selection = aiSelection(config);
  if (config.auth_enabled) throw new Error("This instance uses browser sign-in. Open Jobbr, sign in, and paste the posting in the app; extension sign-in is not yet supported.");
  if (config.llm_enabled) {
    if (typeof confirmAI !== "function") throw new Error("Review and confirm the AI extraction disclosure before saving.");
    if (await confirmAI(aiDisclosure(config)) !== true) return null;
  }
  return apiRequest(base, "/jobs", { token, payload, fetcher, selection });
}

export async function apiRequest(base, path, { token = "", payload, fetcher = fetch, selection } = {}) {
  if (!Object.values(DESTINATIONS).includes(base)) throw new Error("Unsupported Jobbr destination.");
  if (!["/config", "/jobs"].includes(path)) throw new Error("Unsupported Jobbr request.");
  const headers = { Accept: "application/json" };
  if (payload) {
    if (path !== "/jobs" || !selection) throw new Error("Verify extraction settings before saving.");
    Object.assign(headers, selection);
  }
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
