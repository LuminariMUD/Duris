// Browser leg of the disposable MUD -> SQL -> anonymous API handoff.
import assert from "node:assert/strict";
import { readFile, writeFile, mkdtemp, rm } from "node:fs/promises";
import { spawn } from "node:child_process";
import { join } from "node:path";
const base = process.env.PVP_BASE_URL,
  evidence = process.env.PVP_CAPTURE_COMMAND_DIR;
const events = JSON.parse(await readFile(join(evidence, "events.json"), "utf8"));
const profile = await mkdtemp(join(evidence, "browser-"));
const chrome = spawn(
  process.env.PVP_CHROMIUM,
  [
    "--no-sandbox",
    "--disable-gpu",
    "--remote-debugging-port=0",
    "--user-data-dir=" + profile,
    "about:blank",
  ],
  { stdio: ["ignore", "ignore", "pipe"] },
);
let chromeError = "";
chrome.stderr.on("data", (chunk) => (chromeError += chunk));
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let ws;
try {
  let port;
  for (let i = 0; i < 100; i++) {
    try {
      port = Number((await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]);
      break;
    } catch {
      await delay(100);
    }
  }
  assert.ok(port, "Chromium started: " + chromeError);
  const [target] = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });
  let seq = 0;
  const pending = new Map(),
    errors = [];
  const call = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = ++seq;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  ws.onmessage = async ({ data }) => {
    const msg = JSON.parse(data);
    if (msg.id) {
      const p = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? p.reject(Error(JSON.stringify(msg.error))) : p.resolve(msg.result);
      return;
    }
    if (msg.method === "Runtime.exceptionThrown") errors.push(msg.params.exceptionDetails.text);
    if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error")
      errors.push(msg.params.args.map((a) => a.value || a.description).join(" "));
    if (msg.method === "Fetch.requestPaused") {
      try {
        const { requestId, request } = msg.params,
          url = new URL(request.url);
        // The production frontend may use an absolute API URL. Every request is
        // served by the isolated paired router; no public/live origin is contacted.
        if (url.pathname.startsWith("/api/")) {
          const response = await fetch(base + url.pathname + url.search, {
            method: request.method,
            headers: { "Content-Type": "application/json" },
            body: ["GET", "HEAD"].includes(request.method) ? undefined : request.postData,
          });
          await call("Fetch.fulfillRequest", {
            requestId,
            responseCode: response.status,
            responseHeaders: [
              { name: "Content-Type", value: "application/json" },
              { name: "Cache-Control", value: response.headers.get("cache-control") || "no-store" },
              { name: "Access-Control-Allow-Origin", value: base },
              { name: "Access-Control-Allow-Credentials", value: "true" },
              { name: "Access-Control-Allow-Headers", value: "content-type,x-csrf-token" },
              { name: "Access-Control-Allow-Methods", value: "GET,POST,OPTIONS" },
            ],
            body: Buffer.from(await response.text()).toString("base64"),
          });
        } else if (url.origin === base || url.protocol === "data:")
          await call("Fetch.continueRequest", { requestId });
        else await call("Fetch.fulfillRequest", { requestId, responseCode: 204 });
      } catch (error) {
        // Navigation cancels requests that were paused on the previous document.
        if (!String(error).includes("Invalid InterceptionId")) errors.push(String(error));
      }
    }
  };
  await call("Page.enable");
  await call("Runtime.enable");
  await call("Network.enable");
  await call("Fetch.enable", { patterns: [{ urlPattern: "*", requestStage: "Request" }] });
  await call("Page.addScriptToEvaluateOnNewDocument", {
    source: `window.WebSocket=class extends EventTarget { constructor(){super();this.readyState=0;} close(){} send(){} };`,
  });
  const evaluate = async (expression) => {
    const r = await call("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (r.exceptionDetails)
      throw Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  };
  async function until(expression) {
    for (let i = 0; i < 100; i++) {
      if (await evaluate(`!!document.body && (${expression})`)) return;
      await delay(100);
    }
    throw Error(expression + "\n" + (await evaluate("document.body.innerText")));
  }
  const screenshot = async (name) => {
    const result = await call("Page.captureScreenshot", { format: "png" });
    await writeFile(join(evidence, name + ".png"), Buffer.from(result.data, "base64"));
  };
  const click = async (selector) =>
    assert.equal(
      await evaluate(`(()=>{const el=${selector};if(!el)return false;el.click();return true;})()`),
      true,
      selector,
    );
  const visibleButtons = `[...document.querySelectorAll('button')].filter(e=>e.getBoundingClientRect().width>0)`;
  for (const mobile of [false, true]) {
    await call("Emulation.setDeviceMetricsOverride", {
      width: mobile ? 390 : 1440,
      height: mobile ? 844 : 1000,
      deviceScaleFactor: 1,
      mobile,
    });
    for (const [index, name, status] of [
      [0, "Alice", "public"],
      [0, "Bob", "private"],
      [1, "Bob", "public"],
      [2, "Alice", "private"],
      [3, "Alice", "empty"],
      [4, "Alice", "unavailable"],
    ]) {
      await call("Page.navigate", { url: `${base}/pvp/${events[index]}?pov=${name}` });
      const expected =
        status === "public"
          ? name === "Alice"
            ? "PUBLIC_A_LINE"
            : "PUBLIC_B_LINE"
          : status === "private"
            ? "point of view is private"
            : status === "empty"
              ? "No combat log was captured"
              : "point of view is unavailable";
      await until(`document.body.innerText.includes(${JSON.stringify(expected)})`);
      assert.equal(await evaluate(`new URL(location.href).searchParams.get('pov')`), name);
      assert.equal(
        await evaluate(`/PRIVATE_HANDOFF_MARKER|OFF_INTERVAL/.test(document.body.innerText)`),
        false,
      );
      if (status !== "empty") {
        await click(
          mobile
            ? `${visibleButtons}.find(e=>e.textContent.trim()==='Equipment'&&!e.title)`
            : `document.querySelector('button[title="View equipment"]')`,
        );
        await until(
          status === "public"
            ? `document.body.innerText.includes('EQUIPMENT_FIXTURE')`
            : `document.body.innerText.includes(${JSON.stringify(expected)})`,
        );
        if (!mobile) {
          assert.equal(
            await evaluate(
              `document.querySelector('[role="dialog"]').innerText.includes('EQUIPMENT_FIXTURE')`,
            ),
            status === "public",
          );
          await call("Input.dispatchKeyEvent", {
            type: "keyDown",
            key: "Escape",
            code: "Escape",
            windowsVirtualKeyCode: 27,
          });
          await call("Input.dispatchKeyEvent", {
            type: "keyUp",
            key: "Escape",
            code: "Escape",
            windowsVirtualKeyCode: 27,
          });
          await click(`document.querySelector('button[title="Maximize combat log"]')`);
          await until(
            `document.querySelector('[role="dialog"]')?.innerText.includes(${JSON.stringify(expected)})`,
          );
        }
      }
      assert.equal(await evaluate(`!!document.querySelector('vite-error-overlay')`), false);
      await screenshot(`${mobile ? "mobile" : "desktop"}-${index}-${name}-${status}`);
    }
  }
  // Activate the actual built worker with a previous-generation API cache.
  await evaluate(`(async()=>{
   for(const r of await navigator.serviceWorker.getRegistrations())await r.unregister();
   const cache=await caches.open('api-cache');
   await cache.put('/api/pvp/events/${events[0]}',new Response('OLD_POV_CACHE'));
   await cache.put('/api/news/fixture',new Response('KEEP_NEWS_CACHE'));
   const registration=await navigator.serviceWorker.register('/service-worker.js?handoff');
   const worker=registration.installing||registration.waiting||registration.active;
   if(worker.state!=='activated')await new Promise(resolve=>{
     const changed=()=>{if(worker.state==='installed')worker.postMessage({type:'SKIP_WAITING'});if(worker.state==='activated'){worker.removeEventListener('statechange',changed);resolve();}};
     worker.addEventListener('statechange',changed);changed();
   });
 })()`);
  await until(
    `(async()=>{const cache=await caches.open('api-cache');return !(await cache.match('/api/pvp/events/${events[0]}'))&&!!(await cache.match('/api/news/fixture'));})()`,
  );
  await call("Page.navigate", { url: `${base}/pvp/${events[0]}?pov=Alice` });
  await until(`document.body.innerText.includes('PUBLIC_A_LINE')`);
  assert.equal(await evaluate(`!!navigator.serviceWorker.controller`), true);
  await fetch(base + "/fixture/webinfo/off", { method: "POST" });
  await call("Page.reload", { ignoreCache: false });
  await until(`document.body.innerText.includes('point of view is private')`);
  assert.equal(await evaluate(`document.body.innerText.includes('PUBLIC_A_LINE')`), false);
  await fetch(base + "/fixture/webinfo/on", { method: "POST" });
  await call("Page.reload", { ignoreCache: false });
  await until(`document.body.innerText.includes('PUBLIC_A_LINE')`);
  assert.equal(
    await evaluate(
      `(async()=>!!(await (await caches.open('api-cache')).match('/api/pvp/events/${events[0]}')))()`,
    ),
    false,
  );
  assert.deepEqual(errors, []);
  await writeFile(
    join(evidence, "browser-result.json"),
    JSON.stringify(
      {
        events,
        passed: [
          "desktop/mobile direct POV links",
          "private/unavailable messages and controls",
          "public logs, equipment and maximized view",
          "empty public logs",
          "no off-period or private markers",
          "worker activation removes old PvP cache and retains news",
          "saved opt-out and opt-in refresh under controlling worker",
          "no console/page errors",
        ],
      },
      null,
      2,
    ),
  );
  console.log("Paired browser journey passed on desktop and mobile");
} finally {
  ws?.close();
  if (chrome.exitCode === null && chrome.signalCode === null) {
    const exited = new Promise((resolve) => chrome.once("exit", resolve));
    chrome.kill("SIGTERM");
    await exited;
  }
  await rm(profile, { recursive: true, force: true });
}
