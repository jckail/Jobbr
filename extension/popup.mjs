import { apiRequest, destination, jobPayload, MAX_TEXT_LENGTH, postingUrl } from "./core.mjs";

const el = Object.fromEntries(["destination", "open-app", "capture", "preview", "url", "text", "count", "save", "token", "forget", "status"].map(id => [id, document.getElementById(id)]));
let busy = false;
function status(message, error = false) {
  el.status.textContent = message;
  el.status.dataset.error = String(error);
}
function setBusy(value) {
  busy = value;
  for (const id of ["capture", "save", "destination", "token", "forget"]) el[id].disabled = value;
}
function updateCount() { el.count.textContent = `${el.text.value.length.toLocaleString()} / 60,000`; }
function tokenKey() { return `token.${el.destination.value}`; }
async function selectDestination() {
  const base = destination(el.destination.value);
  el["open-app"].href = base + "/";
  el.token.value = (await chrome.storage.session.get(tokenKey()))[tokenKey()] || "";
  await chrome.storage.local.set({ destination: el.destination.value });
  status("");
}

el.destination.addEventListener("change", async () => {
  setBusy(true);
  try { await selectDestination(); }
  catch (e) { status(e.message, true); }
  finally { setBusy(false); }
});
el.token.addEventListener("change", async () => {
  try { await chrome.storage.session.set({ [tokenKey()]: el.token.value.trim() }); }
  catch (e) { status(e.message, true); }
});
el.forget.addEventListener("click", async () => {
  try { await chrome.storage.session.remove(tokenKey()); el.token.value = ""; status("Token forgotten for this destination."); }
  catch (e) { status(e.message, true); }
});
el.text.addEventListener("input", updateCount);
el.capture.addEventListener("click", async () => {
  if (busy) return;
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
    el.url.value = postingUrl(result.result.url);
    el.text.value = result.result.text;
    el.preview.hidden = false;
    updateCount();
    status(result.result.truncated ? "Preview limited to 60,000 characters. Review before saving." : "Preview ready. Review the URL and text before saving.");
  } catch (e) { status(`Capture failed: ${e.message}`, true); }
  finally { setBusy(false); }
});
el.preview.addEventListener("submit", async event => {
  event.preventDefault();
  if (busy) return;
  setBusy(true);
  try {
    const base = destination(el.destination.value);
    const payload = jobPayload(el.url.value, el.text.value);
    const token = el.token.value.trim();
    await chrome.storage.session.set({ [tokenKey()]: token });
    const config = await apiRequest(base, "/config");
    if (config.auth_enabled) throw new Error("This instance uses browser sign-in. Open Jobbr, sign in, and paste the posting in the app; extension sign-in is not yet supported.");
    status("Saving to Jobbr… Keep this popup open until it finishes.");
    const job = await apiRequest(base, "/jobs", { token, payload });
    status(`Saved: ${job.title || "Job posting"}${job.company ? ` at ${job.company}` : ""}. Open Jobbr to review it.`);
  } catch (e) {
    status(e.name === "TimeoutError" || e.name === "TypeError" ? "Could not confirm the save. Check Jobbr before retrying; it may have completed. Check the selected destination and connection." : e.message, true);
  } finally { setBusy(false); }
});

async function init() {
  setBusy(true);
  // Session storage defaults to trusted extension contexts; explicitly preserve that boundary.
  await chrome.storage.session.setAccessLevel({ accessLevel: "TRUSTED_CONTEXTS" });
  const stored = await chrome.storage.local.get("destination");
  el.destination.value = ["local", "production"].includes(stored.destination) ? stored.destination : "local";
  await selectDestination();
  setBusy(false);
}
init().catch(e => { setBusy(false); status(`Could not initialize: ${e.message}`, true); });
