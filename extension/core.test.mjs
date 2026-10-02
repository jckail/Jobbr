import test from "node:test";
import assert from "node:assert/strict";
import { aiSelection, apiRequest, destination, jobPayload, postingUrl, savePosting, MAX_TEXT_LENGTH } from "./core.mjs";

const offlineConfig = { auth_enabled: false, ai_provider: "openai", ai_model: "test-model", llm_enabled: false };

test("destinations are restricted to the two reviewed apps", () => {
  assert.equal(destination("local"), "http://localhost:8000/jobbr");
  assert.equal(destination("production"), "https://jckail.com/jobbr");
  for (const key of ["https://attacker.example", "constructor", "__proto__", "toString"]) assert.throws(() => destination(key));
});
test("posting payload blocks unsafe schemes and credentials, preserves query and strips fragment", () => {
  assert.deepEqual(jobPayload("https://jobs.example/role?id=12#apply", "  Posting\ntext "), { url: "https://jobs.example/role?id=12", text: "Posting\ntext" });
  assert.deepEqual(jobPayload("https://jobs.example/role", " \n"), { url: "https://jobs.example/role" });
  for (const url of ["javascript:alert(1)", "file:///secret", "chrome://settings", "https://user:secret@jobs.example", "invalid"]) assert.throws(() => postingUrl(url));
  assert.throws(() => jobPayload("https://jobs.example", "x".repeat(MAX_TEXT_LENGTH + 1)));
});
test("API sends only to approved destination and blocks redirects and implicit credentials", async () => {
  let request;
  const fetcher = async (url, options) => { request = { url, options }; return { ok: true, json: async () => ({ id: 1 }) }; };
  const payload = { url: "https://jobs.example/role", text: "Posting" };
  assert.deepEqual(await apiRequest(destination("local"), "/jobs", { token: "session-secret", payload, fetcher, selection: aiSelection(offlineConfig) }), { id: 1 });
  assert.equal(request.url, "http://localhost:8000/jobbr/api/jobs");
  assert.equal(request.options.headers["X-Jobbr-Token"], "session-secret");
  assert.equal(request.options.credentials, "omit");
  assert.equal(request.options.redirect, "error");
  assert.deepEqual(JSON.parse(request.options.body), payload);
  await assert.rejects(apiRequest("https://attacker.example", "/jobs", { fetcher }));
  await assert.rejects(apiRequest(destination("local"), "/profile", { fetcher }));
});
test("AI save requires explicit disclosure confirmation before any POST", async () => {
  for (const provider of ["openai", "anthropic"]) {
    const calls = [];
    const config = { ...offlineConfig, ai_provider: provider, llm_enabled: true };
    const fetcher = async (url, options) => {
      calls.push({ url, options });
      return { ok: true, json: async () => url.endsWith("/config") ? config : { id: 2 } };
    };
    const args = { payload: jobPayload("https://jobs.example/role", "posting"), fetcher };
    await assert.rejects(savePosting(destination("local"), args), /confirm the AI/);
    assert.equal(calls.length, 1);
    calls.length = 0;
    assert.equal(await savePosting(destination("local"), { ...args, confirmAI: message => {
      assert.match(message, provider === "anthropic" ? /Anthropic Claude/ : /OpenAI/);
      assert.match(message, /test-model/);
      assert.match(message, /posting text/);
      assert.match(message, /API charges/);
      assert.match(message, /resume is not included/);
      assert.equal(calls.length, 1);
      return false;
    } }), null);
    assert.equal(calls.length, 1);
    calls.length = 0;
    assert.deepEqual(await savePosting(destination("local"), { ...args, confirmAI: () => true }), { id: 2 });
    assert.equal(calls.length, 2);
    assert.equal(calls[1].options.headers["X-Jobbr-AI-Provider"], provider);
    assert.equal(calls[1].options.headers["X-Jobbr-AI-Model"], "test-model");
    assert.equal(calls[1].options.headers["X-Jobbr-AI-Enabled"], "true");
  }
});
test("disabled extraction stays pinned and stale settings fail visibly without retry", async () => {
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, options });
    return url.endsWith("/config") ? { ok: true, json: async () => offlineConfig }
      : { ok: false, status: 409, json: async () => ({ detail: "AI settings changed. Refresh and review the disclosure again." }) };
  };
  await assert.rejects(savePosting(destination("local"), {
    payload: { url: "https://jobs.example/role" }, fetcher,
    confirmAI: () => assert.fail("Disabled AI must not request paid extraction consent"),
  }), /AI settings changed/);
  assert.equal(calls.length, 2);
  assert.deepEqual(Object.fromEntries(Object.entries(calls[1].options.headers).filter(([key]) => key.startsWith("X-Jobbr-AI"))), aiSelection(offlineConfig));
});
test("browser sign-in and unverifiable settings prevent posting transmission", async () => {
  for (const config of [{ ...offlineConfig, auth_enabled: true }, {}, { ...offlineConfig, llm_enabled: "true" }]) {
    let count = 0;
    const fetcher = async () => { count++; return { ok: true, json: async () => config }; };
    await assert.rejects(savePosting(destination("local"), { payload: { url: "https://jobs.example" }, fetcher, confirmAI: () => assert.fail("Must reject before consent") }));
    assert.equal(count, 1);
  }
});
test("locked writes and backend validation return actionable errors", async () => {
  await assert.rejects(apiRequest(destination("local"), "/jobs", { fetcher: async () => ({ ok: false, status: 401 }) }), /Editing is locked/);
  await assert.rejects(apiRequest(destination("local"), "/jobs", { fetcher: async () => ({ ok: false, status: 422, json: async () => ({ detail: "No posting text found" }) }) }), /No posting text found/);
});
