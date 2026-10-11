// Exercise the shipped dashboard script against a real running FastAPI server.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { JSDOM, VirtualConsole } from "jsdom";

const base = process.env.GRIDFLEX_TEST_URL || "http://127.0.0.1:8000";
const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", (e) => errors.push(e.message));
const dom = await JSDOM.fromURL(base, {
  resources: "usable",
  runScripts: "dangerously",
  pretendToBeVisual: true,
  virtualConsole,
  beforeParse(window) {
    // Pair Node's fetch with Node's AbortSignal in this DOM harness.
    window.AbortController = globalThis.AbortController;
    window.fetch = (path, options) => fetch(new URL(path, base), options);
  },
});
const { window } = dom;
const document = window.document;
async function until(predicate) {
  const deadline = Date.now() + 15000;
  while (!predicate()) {
    if (Date.now() > deadline)
      throw new Error(
        `UI condition timed out: ${errors.join("; ")}; ${document.querySelector("#error")?.textContent}`,
      );
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}
await until(
  () => document.querySelectorAll("#forecast-table tr").length === 48,
);
await until(() => document.querySelectorAll("#model-table tr").length === 5);
assert.notEqual(document.querySelector("#mae").textContent, "—");
assert.match(
  document.querySelector("#mode-note").textContent,
  /Historical replay/,
);
assert.equal(document.querySelectorAll("#chart svg").length, 1);
const form = document.querySelector("#charging-form");
form.dispatchEvent(
  new window.Event("submit", { bubbles: true, cancelable: true }),
);
await until(() => !document.querySelector("#result-panel").hidden);
assert.match(document.querySelector("#energy").textContent, /33\.3 kWh/);
assert.equal(document.querySelectorAll("#schedule-chart rect").length, 48);

// Save a static rendering of this real API response for a reviewer, not a live site.
const snapshot = new JSDOM(dom.serialize());
snapshot.window.document
  .querySelectorAll('script,link[rel="stylesheet"]')
  .forEach((e) => e.remove());
const style = snapshot.window.document.createElement("style");
style.textContent = await fs.readFile("src/gridflex/static/style.css", "utf8");
snapshot.window.document.head.append(style);
snapshot.window.document.querySelector("#mode-note").textContent =
  "Static recorded replay from the running API · 21 Sep 2026 · start the app for interaction";
snapshot.window.document
  .querySelectorAll("button,input,select,textarea")
  .forEach((e) => {
    e.disabled = true;
  });
await fs.writeFile(
  "docs/demo-snapshot.html",
  snapshot.serialize().replace(/[ \t]+$/gm, ""),
);
snapshot.window.close();

form.elements.namedItem("hours").value = "1";
form.dispatchEvent(
  new window.Event("submit", { bubbles: true, cancelable: true }),
);
await until(() => !document.querySelector("#error").hidden);
assert.match(document.querySelector("#error").textContent, /infeasible/);
assert.equal(document.querySelector("#result-panel").hidden, true);
await until(() => !document.querySelector("#schedule-button").disabled);
form.elements.namedItem("hours").value = "24";
document.querySelector("#objective").value = "cost";
document.querySelector("#objective").dispatchEvent(new window.Event("change"));
assert.equal(document.querySelector("#prices-label").hidden, false);
form.elements.namedItem("prices").value = "10,20";
form.dispatchEvent(
  new window.Event("submit", { bubbles: true, cancelable: true }),
);
await until(() =>
  document.querySelector("#error").textContent.includes("one price per"),
);
assert.deepEqual(errors, []);
assert.match(
  document.querySelector("#download").href,
  /expected_forecast_id=[a-f0-9]{64}/,
);

// A late response from the previous mode must not overwrite the selected mode.
const realFetch = window.fetch;
let releaseLive;
window.fetch = (path, options) =>
  String(path).includes("forecast?mode=live")
    ? new Promise((resolve) => {
        releaseLive = resolve;
      })
    : realFetch(path, options);
document.querySelector("#live-mode").click();
assert.equal(document.querySelectorAll("#forecast-table tr").length, 0);
document.querySelector("#replay-mode").click();
await until(
  () => document.querySelectorAll("#forecast-table tr").length === 48,
);
const replay = await (await realFetch("/api/v1/forecast?mode=replay")).json();
releaseLive({
  ok: true,
  json: async () => ({
    ...replay,
    mode: "live",
    notice: "STALE LIVE RESPONSE",
  }),
});
await new Promise((resolve) => setTimeout(resolve, 50));
assert.match(
  document.querySelector("#mode-note").textContent,
  /Historical replay/,
);

// Editing a request invalidates a plan even if its response arrives later.
let releasePlan;
window.fetch = (path, options) =>
  String(path) === "/api/v1/schedule"
    ? new Promise((resolve) => {
        releasePlan = async () => resolve(await realFetch(path, options));
      })
    : realFetch(path, options);
document.querySelector("#objective").value = "carbon";
form.dispatchEvent(
  new window.Event("submit", { bubbles: true, cancelable: true }),
);
form.elements.namedItem("capacity").value = "65";
form.dispatchEvent(new window.Event("input", { bubbles: true }));
await releasePlan();
await new Promise((resolve) => setTimeout(resolve, 50));
assert.equal(document.querySelector("#result-panel").hidden, true);
window.close();
console.log(
  "UI integration passed: chart, five benchmarks, feasible schedule, invalid input, forecast binding, mode-response race and edited-request invalidation.",
);
