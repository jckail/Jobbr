import test from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { activeConnection, activePairing, beginConnection, destination, disconnectConnection, finishConnection, pkce, savePosting } from "./core.mjs";

const base = destination("production");
const id = "a".repeat(32);
const requestId = "r".repeat(43);
const secret = "s".repeat(43);
const grant = "g".repeat(43);
const expires = new Date(Date.now() + 60000).toISOString();
const config = { auth_enabled: true, llm_enabled: false, ai_provider: "openai", ai_model: "test-model" };
const connection = { base, extension_id: id, access_token: secret, token_type: "Bearer", scope: "jobs:capture", grant_id: grant, expires_at: expires };
const pairing = { base, extension_id: id, challenge: requestId, verifier: "v".repeat(43), expires_at: expires,
  approval_url: base + "/#/extension-connect/" + id + "/" + requestId, comparison_code: "ABCDEF12" };
const ok = (value, status = 200) => ({ ok: true, status, json: async () => value });

test("Connect creates a local S256 challenge and canonical URL without HTTP requests or secret URL values", async () => {
  const result = await beginConnection(base, id, { cryptoSource: webcrypto,
    fetcher: () => assert.fail("Connect must never send public pairing HTTP requests") });
  const digest = await webcrypto.subtle.digest("SHA-256", new TextEncoder().encode(result.verifier));
  assert.equal(result.challenge, Buffer.from(digest).toString("base64url"));
  assert.equal(result.approval_url, base + "/#/extension-connect/" + id + "/" + result.challenge);
  assert.equal(result.approval_url.includes(result.verifier), false);
  const code = await webcrypto.subtle.digest("SHA-256", new TextEncoder().encode(id + "\n" + result.challenge));
  assert.equal(result.comparison_code, Buffer.from(code).subarray(0, 4).toString("hex").toUpperCase());
  assert.equal(activePairing(result, base, id), result);
});

test("Connect and saved pairing state refuse arbitrary destinations, IDs, expiry or redirected approval routes", async () => {
  await assert.rejects(beginConnection("https://attacker.example", id, { cryptoSource: webcrypto }));
  await assert.rejects(beginConnection(base, "invalid", { cryptoSource: webcrypto }));
  for (const override of [
    { approval_url: "https://attacker.example/#/extension-connect/" + requestId },
    { approval_url: "https://user:password@jckail.com/jobbr/#/extension-connect/" + requestId },
    { approval_url: base + "/?token=private#/extension-connect/" + requestId },
    { approval_url: base + "/#/extension-connect/other" },
    { expires_at: new Date(0).toISOString() }, { challenge: "short" }, { comparison_code: "<html>" },
  ]) assert.throws(() => activePairing({ ...pairing, ...override }, base, id));
});

test("Finish exchanges once without cookies and validates exact capture scope", async () => {
  let call;
  const result = await finishConnection(base, id, pairing, { fetcher: async (url, options) => { call = { url, options }; return ok(connection); } });
  assert.equal(result.access_token, secret);
  assert.equal(call.url, base + "/api/extension/exchange");
  assert.deepEqual(JSON.parse(call.options.body), { extension_id: id, challenge: requestId, verifier: pairing.verifier });
  assert.equal(call.options.credentials, "omit");
  assert.equal(call.options.headers.Authorization, undefined);
  for (const override of [{ scope: "jobs:read" }, { token_type: "Other" }, { grant_id: "short" }, { expires_at: 0 }, { access_token: "short" }]) {
    await assert.rejects(finishConnection(base, id, pairing, { fetcher: async () => ok({ ...connection, ...override }) }));
  }
});

test("expired and destination-separated approvals never exchange or capture", async () => {
  for (const override of [{ base: destination("local") }, { extension_id: "b".repeat(32) }, { expires_at: 0 }]) {
    let calls = 0;
    await assert.rejects(finishConnection(base, id, { ...pairing, ...override }, { fetcher: async () => { calls++; } }));
    assert.equal(calls, 0);
    assert.throws(() => activeConnection({ ...connection, ...override }, base, id));
  }
  assert.throws(() => activePairing({ ...pairing, approval_url: "https://attacker.example" }, base, id));
});

test("pending Finish has no polling, retries or leakage of provider error strings", async () => {
  let calls = 0;
  await assert.rejects(finishConnection(base, id, pairing, { fetcher: async () => {
    calls++; return { ok: false, status: 404, json: async () => ({ detail: "sensitive provider output" }) };
  } }), /Approve this connection/);
  assert.equal(calls, 1);
});

test("direct OIDC capture sends scoped bearer, exact AI pins and idempotency key only after consent", async () => {
  const calls = [];
  const payload = { url: "https://jobs.example/role", text: "reviewed posting" };
  const fetcher = async (url, options) => { calls.push({ url, options }); return ok(url.endsWith("/config") ? { ...config, llm_enabled: true } : { id: 123 }); };
  assert.equal(await savePosting(base, { id, connection, token: "never-send-this-token", requestKey: requestId, payload, fetcher, confirmAI: () => false }), null);
  assert.equal(calls.length, 1);
  calls.length = 0;
  assert.deepEqual(await savePosting(base, { id, connection, token: "never-send-this-token", requestKey: requestId, payload, fetcher, confirmAI: message => {
    assert.match(message, /API charges/); assert.equal(calls.length, 1); return true;
  } }), { id: 123 });
  assert.equal(calls.length, 2);
  const sent = calls[1];
  assert.equal(sent.url, base + "/api/extension/captures");
  assert.equal(sent.options.headers.Authorization, "Bearer " + secret);
  assert.equal(sent.options.headers["X-Jobbr-Extension-ID"], id);
  assert.equal(sent.options.headers["Idempotency-Key"], requestId);
  assert.equal(sent.options.headers["X-Jobbr-AI-Enabled"], "true");
  assert.equal(sent.options.headers["X-Jobbr-AI-Model"], "test-model");
  assert.equal(sent.options.headers["X-Jobbr-AI-Provider"], "openai");
  assert.equal(sent.options.headers["X-Jobbr-Token"], undefined);
  assert.equal(sent.options.headers["X-CSRF-Token"], undefined);
  assert.deepEqual(JSON.parse(sent.options.body), payload);
  assert.equal(sent.url.includes(secret), false);
});

test("disabled AI direct capture pins false; scope expiry, missing request IDs and failures do not retry", async () => {
  const payload = { url: "https://jobs.example/role" };
  for (const code of [401, 403, 409, 429, 500]) {
    const calls = [];
    const fetcher = async (url, options) => {
      calls.push({ url, options });
      return url.endsWith("/config") ? ok(config) : { ok: false, status: code, json: async () => ({ detail: secret }) };
    };
    await assert.rejects(savePosting(base, { id, connection, requestKey: requestId, payload, fetcher, confirmAI: () => assert.fail("offline must not ask paid consent") }), error => !error.message.includes(secret));
    assert.equal(calls.length, 2);
    assert.equal(calls[1].options.headers["X-Jobbr-AI-Enabled"], "false");
  }
  let calls = 0;
  await assert.rejects(savePosting(base, { id, connection, payload, fetcher: async () => { calls++; return ok(config); } }));
  assert.equal(calls, 1);
});

test("capture network uncertainty and invalid receipts never claim success or retry", async () => {
  for (const outcome of ["network", "bad-json", "missing-id"]) {
    let calls = 0;
    const fetcher = async url => {
      calls++;
      if (url.endsWith("/config")) return ok(config);
      if (outcome === "network") throw new TypeError("connection unavailable");
      if (outcome === "bad-json") return { ok: true, status: 200, json: async () => { throw new Error("secret"); } };
      return ok({ title: "unverifiable" });
    };
    await assert.rejects(savePosting(base, { id, connection, requestKey: requestId, payload: { url: "https://jobs.example" }, fetcher }), /Check Jobbr/);
    assert.equal(calls, 2);
  }
});

test("disconnect can revoke only its own scope, without website credentials", async () => {
  let call;
  assert.equal(await disconnectConnection(base, id, connection, { fetcher: async (url, options) => { call = { url, options }; return ok(null, 204); } }), null);
  assert.equal(call.url, base + "/api/extension/disconnect");
  assert.equal(call.options.headers.Authorization, "Bearer " + secret);
  assert.equal(call.options.credentials, "omit");
  assert.deepEqual(JSON.parse(call.options.body), {});
});


test("approval expiring during paid consent prevents posting transmission", async () => {
  const expiring = { ...connection };
  let calls = 0;
  await assert.rejects(savePosting(base, { id, connection: expiring, requestKey: requestId,
    payload: { url: "https://jobs.example/role", text: "posting" },
    fetcher: async () => { calls++; return ok({ ...config, llm_enabled: true }); },
    confirmAI: () => { expiring.expires_at = 0; return true; },
  }), /missing or expired/);
  assert.equal(calls, 1);
});
