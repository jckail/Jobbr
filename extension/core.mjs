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

export async function savePosting(base, { token = "", payload, fetcher = fetch, confirmAI, connection, id, requestKey } = {}) {
  const config = await apiRequest(base, "/config", { fetcher });
  const selection = aiSelection(config);
  if (config.auth_enabled) activeConnection(connection, base, id);
  if (config.llm_enabled) {
    if (typeof confirmAI !== "function") throw new Error("Review and confirm the AI extraction disclosure before saving.");
    if (await confirmAI(aiDisclosure(config)) !== true) return null;
  }
  if (config.auth_enabled) {
    activeConnection(connection, base, id);
    if (!opaque(requestKey)) throw new Error("A new capture request identity is required before saving.");
    const receipt = await extensionRequest(base, "/extension/captures", { id, connection, payload, fetcher, selection, requestKey });
    if (!receipt || !Number.isSafeInteger(receipt.id) || receipt.id < 1) {
      throw new ExtensionError("Could not verify the save receipt. Check Jobbr before sending again; no retry was made.");
    }
    return { id: receipt.id };
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

export class ExtensionError extends Error {
  constructor(message, status = 0) { super(message); this.name = "ExtensionError"; this.status = status; }
}

export function extensionId(value) {
  if (typeof value !== "string" || !/^[a-p]{32}$/.test(value)) throw new Error("Could not verify this extension's ID.");
  return value;
}
function opaque(value) { return typeof value === "string" && /^[A-Za-z0-9_-]{43}$/.test(value); }
export function expiresAt(value) {
  const date = typeof value === "number" ? value * 1000 : typeof value === "string" ? Date.parse(value) : NaN;
  if (!Number.isFinite(date)) throw new Error("Could not verify connection expiry.");
  return date;
}
export function activeConnection(connection, base, id, now = Date.now()) {
  if (!connection || connection.base !== base || connection.extension_id !== extensionId(id)
    || !opaque(connection.access_token) || !opaque(connection.grant_id)
    || connection.token_type !== "Bearer" || connection.scope !== "jobs:capture"
    || expiresAt(connection.expires_at) <= now) {
    throw new ExtensionError("Connect this extension to the selected Jobbr workspace again; its approval is missing or expired.", 401);
  }
  return connection;
}
export function randomSecret(cryptoSource = globalThis.crypto) {
  const bytes = cryptoSource.getRandomValues(new Uint8Array(32));
  return btoa(String.fromCharCode(...bytes)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}
export async function pkce(cryptoSource = globalThis.crypto) {
  const verifier = randomSecret(cryptoSource);
  const digest = new Uint8Array(await cryptoSource.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
  const challenge = btoa(String.fromCharCode(...digest)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
  return { verifier, challenge };
}
async function extensionRequest(base, path, { payload, connection, id, requestKey, selection, fetcher = fetch } = {}) {
  if (!Object.values(DESTINATIONS).includes(base)) throw new Error("Unsupported Jobbr destination.");
  if (!["/extension/exchange", "/extension/captures", "/extension/disconnect"].includes(path)) throw new Error("Unsupported extension request.");
  const headers = { Accept: "application/json", "Content-Type": "application/json", "X-Jobbr-Extension-ID": extensionId(id) };
  if (connection) headers.Authorization = "Bearer " + connection.access_token;
  if (requestKey) headers["Idempotency-Key"] = requestKey;
  if (selection) Object.assign(headers, selection);
  let response;
  try {
    response = await fetcher(base + "/api" + path, {
      method: "POST", headers, body: JSON.stringify(payload ?? {}),
      credentials: "omit", redirect: "error", cache: "no-store", signal: AbortSignal.timeout(90000),
    });
  } catch {
    throw new ExtensionError(path === "/extension/captures"
      ? "Could not confirm the save. It may have completed. Check Jobbr before sending again; no retry was made."
      : "Could not confirm the connection request. No automatic retry was made. Reopen Jobbr to check approval or revoke access.");
  }
  if (!response.ok) {
    const messages = {
      401: "Connection is missing, expired or revoked. Connect again; no retry was made.",
      404: "Approve this connection in Jobbr first, then choose Finish connection. No automatic retry was made.",
      403: "This extension or request is not approved for this workspace. Review access in Jobbr.",
      409: path === "/extension/exchange" ? "Approval is pending or already used. Approve in Jobbr, then choose Finish connection; no automatic retry was made."
        : "Capture or AI settings changed, or another save is still pending. Check Jobbr before trying again; no retry was made.",
      410: "This pairing or connection has expired. Start a new connection.",
      422: "Jobbr rejected the connection or posting. Review the URL, text and approved extension ID.",
      429: "The connection or capture limit was reached. Wait or review access in Jobbr; no retry was made.",
    };
    throw new ExtensionError(messages[response.status] ?? "Jobbr could not complete this request. Check Jobbr before trying again; no retry was made.", response.status);
  }
  if (response.status === 204) return null;
  try { return await response.json(); }
  catch { throw new ExtensionError("Jobbr returned an unverifiable result. Check Jobbr before trying again; no retry was made."); }
}
export async function beginConnection(base, id, { cryptoSource = globalThis.crypto } = {}) {
  if (!Object.values(DESTINATIONS).includes(base)) throw new Error("Unsupported Jobbr destination.");
  extensionId(id);
  const { verifier, challenge } = await pkce(cryptoSource);
  const codeHash = new Uint8Array(await cryptoSource.subtle.digest("SHA-256", new TextEncoder().encode(id + "\n" + challenge)));
  const comparison_code = [...codeHash].slice(0, 4).map(byte => byte.toString(16).padStart(2, "0")).join("").toUpperCase();
  return { base, extension_id: id, verifier, challenge,
    approval_url: base + "/#/extension-connect/" + id + "/" + challenge,
    comparison_code, expires_at: new Date(Date.now() + 10 * 60000).toISOString() };
}
export function activePairing(pairing, base, id, now = Date.now()) {
  if (!pairing || pairing.base !== base || pairing.extension_id !== extensionId(id)
    || !opaque(pairing.verifier) || !opaque(pairing.challenge) || expiresAt(pairing.expires_at) <= now
    || pairing.approval_url !== base + "/#/extension-connect/" + id + "/" + pairing.challenge
    || typeof pairing.comparison_code !== "string" || !/^[A-F0-9]{8}$/.test(pairing.comparison_code)) {
    throw new ExtensionError("Pairing is missing or expired. Choose Connect to Jobbr again.", 410);
  }
  return pairing;
}
export async function finishConnection(base, id, pairing, { fetcher = fetch } = {}) {
  activePairing(pairing, base, id);
  const response = await extensionRequest(base, "/extension/exchange", {
    id, payload: { extension_id: id, challenge: pairing.challenge, verifier: pairing.verifier }, fetcher,
  });
  const connection = { base, extension_id: id, access_token: response?.access_token,
    token_type: response?.token_type, expires_at: response?.expires_at, scope: response?.scope, grant_id: response?.grant_id };
  activeConnection(connection, base, id);
  return connection;
}
export async function disconnectConnection(base, id, connection, { fetcher = fetch } = {}) {
  activeConnection(connection, base, id);
  return extensionRequest(base, "/extension/disconnect", { id, connection, fetcher });
}
