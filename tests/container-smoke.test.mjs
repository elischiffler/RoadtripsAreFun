import assert from "node:assert/strict";
import test from "node:test";

const request = (url, options = {}) =>
  fetch(url, { ...options, signal: AbortSignal.timeout(10000) });
test("API exposes honest liveness/readiness and controlled CORS", async () => {
  const api = "http://127.0.0.1:8002";
  assert.equal((await request(`${api}/health`)).status, 200);
  const ready = await request(`${api}/ready`);
  assert.equal(
    ready.status,
    503,
    "The schema-blocked preview must not claim readiness",
  );
  assert.equal((await ready.json()).status, "not_ready");
  assert.equal((await request(`${api}/get-gas-price`)).status, 503);
  for (const [origin, allowed] of [
    ["http://127.0.0.1:8082", true],
    ["https://unapproved.example", false],
  ]) {
    const response = await request(`${api}/health`, {
      method: "OPTIONS",
      headers: { Origin: origin, "Access-Control-Request-Method": "GET" },
    });
    assert.equal(
      response.headers.get("access-control-allow-origin") === origin,
      allowed,
    );
  }
});
test("production frontend serves navigation and explicit local destinations", async () => {
  const web = "http://127.0.0.1:8082";
  assert.equal(await (await request(`${web}/healthz`)).text(), "ok\n");
  const html = await (await request(web)).text();
  assert.equal(await (await request(`${web}/login`)).text(), html);
  assert.equal((await request(`${web}/assets/missing.js`)).status, 404);
  const path = html.match(/src="(\/assets\/[^" ]+\.js)"/)[1];
  const response = await request(`${web}${path}`);
  assert.match(response.headers.get("cache-control"), /immutable/);
  const script = await response.text();
  assert.ok(script.includes("http://127.0.0.1:8002/"));
  assert.ok(script.includes("http://127.0.0.1:8999"));
});
