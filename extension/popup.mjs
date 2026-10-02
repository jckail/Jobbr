import { activeConnection, activePairing, beginConnection, disconnectConnection, finishConnection, randomSecret,
  savePosting, destination, expiresAt, jobPayload, MAX_TEXT_LENGTH, postingUrl } from "./core.mjs";

const ids = ["destination", "open-app", "capture", "preview", "url", "text", "count", "save", "token", "forget", "status",
  "connect", "finish", "disconnect", "connection-status", "extension-id", "pairing-code", "approval-link"];
const el = Object.fromEntries(ids.map(id => [id, document.getElementById(id)]));
let busy = false;
let connection = null;
let pairing = null;
let storageReady = false;
const id = chrome.runtime.id;
function status(message, error = false) {
  el.status.textContent = message;
  el.status.dataset.error = String(error);
}
function key(kind) { return `${kind}.${el.destination.value}`; }
function renderConnection() {
  let connected = false;
  try { if (connection) { activeConnection(connection, destination(el.destination.value), id); connected = true; } }
  catch { /* Expiry is checked again before every request. */ }
  const pending = pairing && expiresAt(pairing.expires_at) > Date.now();
  el["connection-status"].textContent = connected
    ? `Connected for captures until ${new Date(expiresAt(connection.expires_at)).toLocaleTimeString()}. Up to five saves; signing out of Jobbr revokes access.`
    : pending ? "Approve this request in Jobbr, then reopen this popup and choose Finish connection."
      : connection || pairing ? "Connection or pairing expired. Choose Connect to Jobbr again." : "Not connected. Connect for a workspace using browser sign-in.";
  el["pairing-code"].textContent = pending ? `Compare this code in Jobbr: ${pairing.comparison_code}` : "";
  el["approval-link"].hidden = !pending;
  if (pending) el["approval-link"].href = pairing.approval_url;
  else el["approval-link"].removeAttribute("href");
  el.finish.disabled = busy || !storageReady || !pending;
  el.disconnect.disabled = busy || !storageReady || !(connection || pairing);
}
function setBusy(value) {
  busy = value;
  for (const name of ["capture", "save", "destination", "token", "forget", "connect"]) el[name].disabled = value || !storageReady;
  renderConnection();
}
function updateCount() { el.count.textContent = `${el.text.value.length.toLocaleString()} / 60,000`; }
async function selectDestination() {
  const base = destination(el.destination.value);
  el["open-app"].href = base + "/";
  el.token.value = ""; connection = null; pairing = null;
  const keys = [key("token"), key("connection"), key("pairing")];
  const stored = await chrome.storage.session.get(keys);
  el.token.value = stored[key("token")] || "";
  connection = stored[key("connection")] || null;
  pairing = stored[key("pairing")] || null;
  // Reject stale/corrupt storage; never navigate using unchecked persisted URLs.
  try { if (connection) activeConnection(connection, base, id); }
  catch { connection = null; await chrome.storage.session.remove(key("connection")); }
  try { if (pairing) activePairing(pairing, base, id); }
  catch { pairing = null; await chrome.storage.session.remove(key("pairing")); }
  await chrome.storage.local.set({ destination: el.destination.value });
  status(""); renderConnection();
}
el.destination.addEventListener("change", async () => {
  setBusy(true);
  try { await selectDestination(); }
  catch { storageReady = false; connection = null; pairing = null; el.token.value = ""; status("Could not load destination settings. Reload this extension before saving.", true); }
  finally { setBusy(false); }
});
el.token.addEventListener("change", async () => {
  try { await chrome.storage.session.set({ [key("token")]: el.token.value.trim() }); }
  catch { status("Could not keep the API token in session storage.", true); }
});
el.forget.addEventListener("click", async () => {
  try { await chrome.storage.session.remove(key("token")); el.token.value = ""; status("Token forgotten for this destination."); }
  catch { status("Could not forget the token. Reload the extension to clear its session.", true); }
});
el.connect.addEventListener("click", async () => {
  if (busy || !storageReady) return;
  setBusy(true);
  try {
    if (connection) {
      let live = false;
      try { activeConnection(connection, destination(el.destination.value), id); live = true; } catch { /* Expired grants carry no authority. */ }
      if (live) throw new Error("Disconnect the existing capture approval before starting another connection.");
      await chrome.storage.session.remove(key("connection")); connection = null;
    }
    const base = destination(el.destination.value);
    const pending = await beginConnection(base, id);
    await chrome.storage.session.set({ [key("pairing")]: pending });
    pairing = pending;
    renderConnection();
    status("A connection request was created. Review its code, destination and capture permissions in Jobbr. No posting was sent.");
    await chrome.tabs.create({ url: pairing.approval_url });
  } catch (e) { status(e.message, true); }
  finally { setBusy(false); }
});
el.finish.addEventListener("click", async () => {
  if (busy || !storageReady) return;
  setBusy(true);
  try {
    const approved = await finishConnection(destination(el.destination.value), id, pairing);
    await chrome.storage.session.set({ [key("connection")]: approved });
    connection = approved;
    await chrome.storage.session.remove(key("pairing")); pairing = null;
    status("Connected for direct posting captures. Review your posting before Save; AI extraction still needs confirmation.");
  } catch (e) {
    if (e.status === 401 || e.status === 410) { await chrome.storage.session.remove(key("pairing")); pairing = null; }
    status(e.message, true);
  } finally { setBusy(false); }
});
el.disconnect.addEventListener("click", async () => {
  if (busy || !storageReady) return;
  setBusy(true);
  const previous = connection;
  try {
    await chrome.storage.session.remove([key("connection"), key("pairing")]);
    connection = null; pairing = null;
    if (previous) {
      await disconnectConnection(destination(el.destination.value), id, previous);
      status("Capture connection revoked and forgotten for this destination.");
    } else status("Pairing forgotten locally. Any approved access can also be revoked in Jobbr; approved requests expire after five minutes; local pending connection details expire after ten minutes.");
  } catch {
    status("Connection was forgotten locally if storage removal succeeded. Server revocation was not confirmed. Revoke access in Jobbr or wait for expiry; no retry was made.", true);
  } finally { setBusy(false); }
});
el.text.addEventListener("input", updateCount);
el.capture.addEventListener("click", async () => {
  if (busy || !storageReady) return;
  setBusy(true);
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error("Open a job posting in a normal browser tab.");
    postingUrl(tab.url || "");
    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id }, args: [MAX_TEXT_LENGTH],
      func: limit => ({ url: location.href, text: (document.body?.innerText || "").slice(0, limit), truncated: (document.body?.innerText || "").length > limit }),
    });
    if (!result?.result) throw new Error("Could not read this tab. Paste a posting into Jobbr instead.");
    el.url.value = postingUrl(result.result.url); el.text.value = result.result.text;
    el.preview.hidden = false; updateCount();
    status(result.result.truncated ? "Preview limited to 60,000 characters. Review before saving." : "Preview ready. Review the URL and text before saving.");
  } catch (e) { status(`Capture failed: ${e.message}`, true); }
  finally { setBusy(false); }
});
el.preview.addEventListener("submit", async event => {
  event.preventDefault();
  if (busy || !storageReady) return;
  setBusy(true);
  try {
    const base = destination(el.destination.value);
    const payload = jobPayload(el.url.value, el.text.value);
    const token = el.token.value.trim();
    await chrome.storage.session.set({ [key("token")]: token });
    status("Checking extraction settings… Keep this popup open until it finishes.");
    const job = await savePosting(base, { token, payload, connection, id, requestKey: randomSecret(), confirmAI: message => {
      const accepted = window.confirm(message);
      if (accepted) status("Saving to Jobbr… Keep this popup open until it finishes.");
      return accepted;
    } });
    if (!job) { status("Save canceled. No posting was sent."); return; }
    status(`Saved: ${job.title || "Job posting"}${job.company?.name ? ` at ${job.company.name}` : ""}. Open Jobbr to review it.`);
  } catch (e) {
    if (e.status === 401) { connection = null; await chrome.storage.session.remove(key("connection")); }
    status(e.name === "TimeoutError" || e.name === "TypeError" ? "Could not confirm the save. Check Jobbr before retrying; it may have completed. No retry was made." : e.message, true);
  } finally { setBusy(false); }
});
async function init() {
  setBusy(true);
  await chrome.storage.session.setAccessLevel({ accessLevel: "TRUSTED_CONTEXTS" });
  storageReady = true;
  el["extension-id"].textContent = id;
  const stored = await chrome.storage.local.get("destination");
  el.destination.value = ["local", "production"].includes(stored.destination) ? stored.destination : "local";
  await selectDestination(); setBusy(false);
}
init().catch(() => { storageReady = false; setBusy(false); status("Could not initialize trusted session storage. Reload the extension before connecting or saving.", true); });
