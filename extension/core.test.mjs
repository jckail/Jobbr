import test from "node:test";
import assert from "node:assert/strict";
import { apiRequest, destination, jobPayload, postingUrl, MAX_TEXT_LENGTH } from "./core.mjs";

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
  assert.deepEqual(await apiRequest(destination("local"), "/jobs", { token: "session-secret", payload, fetcher }), { id: 1 });
  assert.equal(request.url, "http://localhost:8000/jobbr/api/jobs");
  assert.equal(request.options.headers["X-Jobbr-Token"], "session-secret");
  assert.equal(request.options.credentials, "omit");
  assert.equal(request.options.redirect, "error");
  assert.deepEqual(JSON.parse(request.options.body), payload);
  await assert.rejects(apiRequest("https://attacker.example", "/jobs", { fetcher }));
  await assert.rejects(apiRequest(destination("local"), "/profile", { fetcher }));
});
test("locked writes and backend validation return actionable errors", async () => {
  await assert.rejects(apiRequest(destination("local"), "/jobs", { fetcher: async () => ({ ok: false, status: 401 }) }), /Editing is locked/);
  await assert.rejects(apiRequest(destination("local"), "/jobs", { fetcher: async () => ({ ok: false, status: 422, json: async () => ({ detail: "No posting text found" }) }) }), /No posting text found/);
});
