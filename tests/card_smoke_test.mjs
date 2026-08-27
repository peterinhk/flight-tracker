/**
 * Smoke test for custom_components/flight_tracker/www/flight-tracker-card.js.
 *
 * The card ships as a no-build ES module that Home Assistant injects with
 * add_extra_js_url(), so the browser evaluates it during frontend boot -
 * before any Lovelace element exists. A module-scope failure there is
 * invisible to Python tests and shows up only as "Custom element doesn't
 * exist: flight-tracker-card" on the dashboard, so it is checked here.
 *
 * Run: node tests/card_smoke_test.mjs
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const CARD_PATH = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "custom_components",
  "flight_tracker",
  "www",
  "flight-tracker-card.js"
);
const CARD_TAG = "flight-tracker-card";
const source = readFileSync(CARD_PATH, "utf8");

/** Minimal stand-in for the browser globals the card touches. */
function makeBrowser() {
  const defined = new Map();
  const waiters = new Map();
  const window = {};
  const customElements = {
    get: (tag) => defined.get(tag),
    define(tag, ctor) {
      if (defined.has(tag)) {
        throw new Error(`duplicate definition of <${tag}>`);
      }
      defined.set(tag, ctor);
      (waiters.get(tag) || []).forEach((resolve) => resolve(ctor));
      waiters.delete(tag);
    },
    whenDefined: (tag) =>
      defined.has(tag)
        ? Promise.resolve(defined.get(tag))
        : new Promise((resolve) => waiters.set(tag, (waiters.get(tag) || []).concat(resolve))),
  };
  return { defined, window, customElements };
}

/** Stand-in for Home Assistant's bundled LitElement and a hui-* element. */
function makeLovelaceElement() {
  class LitElement {}
  LitElement.prototype.html = () => {};
  LitElement.prototype.css = () => {};
  class HuiView extends LitElement {}
  return { LitElement, HuiView };
}

function loadCard(browser) {
  // The card has no imports/exports, so a plain function body is a faithful
  // stand-in for evaluating it as a module.
  new Function("window", "customElements", source)(browser.window, browser.customElements);
}

/** Let the card's whenDefined() continuation run. */
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

function pickerEntries(browser) {
  return (browser.window.customCards || []).filter((c) => c.type === CARD_TAG);
}

// --- Lovelace elements absent at load time (the add_extra_js_url case) ------
{
  const browser = makeBrowser();
  const { LitElement, HuiView } = makeLovelaceElement();

  // Must not throw: a module-scope throw aborts the file before it can ever
  // reach customElements.define(), so the card tag never gets registered.
  loadCard(browser);

  assert.equal(
    pickerEntries(browser).length,
    1,
    "card should offer itself to the picker immediately, without waiting for LitElement"
  );

  browser.customElements.define("hui-view", HuiView);
  await flush();

  const card = browser.defined.get(CARD_TAG);
  assert.ok(card, "card must be defined once a Lovelace element appears");
  assert.equal(
    Object.getPrototypeOf(card),
    LitElement,
    "card should extend Home Assistant's own LitElement"
  );
  for (const method of ["setConfig", "getCardSize", "render"]) {
    assert.equal(typeof card.prototype[method], "function", `card must implement ${method}()`);
  }
}

// --- Lovelace elements already present (a lazily-loaded resource) -----------
{
  const browser = makeBrowser();
  const { HuiView } = makeLovelaceElement();
  browser.customElements.define("hui-view", HuiView);

  loadCard(browser);
  await flush();

  assert.ok(browser.defined.get(CARD_TAG), "card must be defined when LitElement is already available");
  assert.equal(pickerEntries(browser).length, 1);
}

// --- Evaluated twice (registered as both an extra JS URL and a resource) ----
{
  const browser = makeBrowser();
  const { HuiView } = makeLovelaceElement();
  browser.customElements.define("hui-view", HuiView);

  loadCard(browser);
  loadCard(browser);
  await flush();

  assert.ok(browser.defined.get(CARD_TAG));
  assert.equal(pickerEntries(browser).length, 1, "picker entry must not be duplicated");
}

console.log("flight-tracker-card.js: all smoke tests passed");
