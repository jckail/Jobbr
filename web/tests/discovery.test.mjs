import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { URL } from "node:url";
import { runInNewContext } from "node:vm";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const jsx = require("react/jsx-runtime");
const source = readFileSync(new URL("../src/components/DiscoveryPanel.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2021, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;

// Execute the actual component's handlers against a small state/API fixture.
// DOM, effects and accessibility still require rendered browser acceptance.
function harness(jobs = []) {
  const state = [];
  let cursor = 0;
  const searches = [], saves = [];
  const config = { llm_enabled: false, career_enabled: false };
  const api = {
    config: async () => config,
    jobs: async () => jobs,
    discover: async (...args) => {
      searches.push(args);
      return { provider: args[0], board: args[1], fetched_at: "2026-10-02T00:00:00Z",
        source_url: "https://jobs.lever.co/second", truncated: false, skipped_unsafe_links: 0,
        postings: [{ source_id: "role", title: "Engineer", company: null, location: "Seattle",
          remote_policy: "remote", url: "https://jobs.lever.co/second/role", raw_text: "Python" }] };
    },
    addJob: async (...args) => { saves.push(args); return { id: 7 }; },
  };
  const hooks = {
    useState: (initial) => {
      const index = cursor++;
      if (!(index in state)) state[index] = initial;
      return [state[index], (value) => { state[index] = typeof value === "function" ? value(state[index]) : value; }];
    },
    useRef: (initial) => {
      const index = cursor++;
      if (!(index in state)) state[index] = { current: initial };
      return state[index];
    },
  };
  const module = { exports: {} };
  runInNewContext(compiled, { module, exports: module.exports, require: (name) => {
    if (name === "react") return hooks;
    if (name === "react/jsx-runtime") return jsx;
    if (name === "../api") return { api, errorMessage: (error) => String(error) };
    if (name === "../util") return { cap: (value) => value };
    if (name === "../ui") return { useAsync: () => ({ loading: false, error: null, data: config }) };
    throw new Error(`Unexpected dependency ${name}`);
  } });
  function nodes() {
    cursor = 0;
    const found = [];
    function visit(node) {
      if (Array.isArray(node)) return node.forEach(visit);
      if (!node || typeof node !== "object" || !node.props) return;
      found.push(node);
      visit(node.props.children);
    }
    visit(module.exports.default({ onSaved: () => {} }));
    return found;
  }
  function find(type, predicate = () => true) {
    const result = nodes().find((node) => node.type === type && predicate(node.props));
    assert.ok(result, `Missing ${type}`);
    return result;
  }
  return { searches, saves, find, nodes,
    provider: (value) => find("select").props.onChange({ target: { value } }),
    board: (value) => find("input", (props) => props.placeholder?.includes("board token")).props.onChange({ target: { value } }),
    employer: (value) => find("input", (props) => props.placeholder?.includes("Required when")).props.onChange({ target: { value } }),
    companyValue: () => find("input", (props) => props.placeholder?.includes("Required when")).props.value,
    search: () => find("form").props.onSubmit({ preventDefault() {} }),
  };
}

test("Greenhouse cannot retain or transmit Lever's remote-only filter", async () => {
  const app = harness();
  assert.equal(app.find("input", (props) => props.type === "checkbox").props.disabled, true);
  app.provider("lever");
  app.board("second");
  app.find("input", (props) => props.type === "checkbox").props.onChange({ target: { checked: true } });
  await app.search();
  assert.equal(app.searches[0][3], "remote");
  app.provider("greenhouse");
  assert.equal(app.find("input", (props) => props.type === "checkbox").props.checked, false);
  await app.search();
  assert.equal(app.searches[1][3], "");
});

test("a different board cannot save a role under the previous employer", async () => {
  const app = harness();
  app.provider("lever");
  app.board("first");
  app.employer("First employer");
  app.board("second");
  assert.equal(app.companyValue(), "");
  await app.search();
  await app.find("button", (props) => props.children === "Save to my jobs").props.onClick();
  assert.equal(app.saves.length, 0);
  assert.match(app.find("p", (props) => props.role === "alert").props.children, /Enter the hiring company/);
  app.employer("Second employer");
  await app.find("button", (props) => props.children === "Save to my jobs").props.onClick();
  assert.equal(app.saves.length, 1);
  assert.equal(app.saves[0][0].company, "Second employer");
});

test("changing provider clears its manual employer override", () => {
  const app = harness();
  app.employer("Previous employer");
  app.provider("lever");
  assert.equal(app.companyValue(), "");
});

test("a unique canonical alias opens the saved role without another save", async () => {
  const app = harness([{ id: 42, url: "https://jobs.lever.co/second/role?source=old",
    external_identity: { provider: "lever", board: "second", posting_id: "role" } }]);
  app.provider("lever");
  app.board("second");
  await app.search();
  assert.equal(app.find("a", (props) => props.children === "Open saved role").props.href, "#/jobs/42");
  assert.equal(app.nodes().some((node) => node.type === "button" && node.props.children === "Save to my jobs"), false);
  assert.equal(app.saves.length, 0);
});

test("ambiguous canonical matches require review without choosing a job", async () => {
  const app = harness([42, 43].map((id) => ({ id, url: `https://jobs.lever.co/second/role?old=${id}`,
    external_identity: { provider: "lever", board: "second", posting_id: "role" } })));
  app.provider("lever");
  app.board("second");
  await app.search();
  assert.equal(app.find("a", (props) => props.children === "Review matching saved roles").props.href, "#/jobs");
  assert.equal(app.nodes().some((node) => node.props.children === "Open saved role" || node.props.children === "Save to my jobs"), false);
  assert.equal(app.saves.length, 0);
});
