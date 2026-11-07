import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { chromium } from "../guidedjourney/node_modules/playwright-core/index.mjs";
const origin = "http://127.0.0.1:5199";
const output = join(import.meta.dirname, ".artifacts");
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-background-networking",
  ],
  headless: true,
});
const errors = [],
  blocked = [];
async function fixture({ conflict = false } = {}) {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  const writes = [];
  let revision = "a".repeat(64);
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) {
      blocked.push(url.origin);
      return route.abort();
    }
    if (url.pathname.startsWith("/api/")) {
      assert.equal(url.pathname, "/api/chats/update/731");
      assert.equal(route.request().method(), "PUT");
      const body = route.request().postDataJSON();
      assert.equal(body.ExpectedRevision, revision);
      assert.equal(body.UpdateScope, "presentation");
      assert.deepEqual(Object.keys(body.ChatData.presentation).sort(), [
        "futureField",
        "visitedStopIds",
      ]);
      writes.push({
        expectedRevision: body.ExpectedRevision,
        presentation: body.ChatData.presentation,
      });
      revision = String.fromCharCode("a".charCodeAt(0) + writes.length).repeat(
        64,
      );
      return route.fulfill({
        status: conflict ? 409 : 200,
        contentType: "application/json",
        body: JSON.stringify(
          conflict
            ? { detail: "Saved trip changed; reload before editing" }
            : { savedRevision: revision },
        ),
      });
    }
    return route.continue();
  });
  await context.addInitScript(() => {
    let success,
      error,
      active = false;
    window.arrivalFixture = {
      watches: 0,
      clears: 0,
      send: (changes = {}) =>
        success?.({
          timestamp: Date.now(),
          coords: {
            latitude: 40,
            longitude: -105,
            accuracy: 10,
            speed: 0,
            ...changes,
          },
        }),
      deny: () => error?.({ code: 1 }),
      get active() {
        return active;
      },
    };
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        watchPosition: (ok, fail) => {
          success = ok;
          error = fail;
          active = true;
          window.arrivalFixture.watches++;
          return 91;
        },
        clearWatch: () => {
          active = false;
          window.arrivalFixture.clears++;
        },
      },
    });
  });
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(error.message));
  await page.clock.setFixedTime(new Date("2030-05-04T12:00:00Z"));
  await page.goto(origin);
  await page
    .getByRole("region", { name: "Arrival assist", exact: true })
    .waitFor();
  assert.equal(await page.evaluate(() => window.arrivalFixture.watches), 0);
  return { context, page, writes };
}
const enable = (page) =>
  page
    .getByRole("button", {
      name: "Enable location and mark nearby stops visited",
      exact: true,
    })
    .click();
async function advance(page, milliseconds) {
  const now = await page.evaluate(() => Date.now());
  await page.clock.setFixedTime(new Date(now + milliseconds));
}
async function dwell(page) {
  for (let index = 0; index < 4; index++) {
    if (index) await advance(page, 15000);
    await page.evaluate(() => window.arrivalFixture.send());
  }
}
try {
  const good = await fixture();
  await enable(good.page);
  await good.page.evaluate(() =>
    window.arrivalFixture.send({ accuracy: 1000 }),
  );
  assert.equal(good.writes.length, 0);
  await advance(good.page, 1000);
  await dwell(good.page);
  await good.page.getByText("Visit updates saved.", { exact: true }).waitFor();
  await good.page
    .getByText("Detected arrival: Synthetic arrival garden", { exact: true })
    .waitFor();
  assert.equal(good.writes.length, 1);
  assert.equal(
    await good.page.evaluate(() => window.arrivalFixture.active),
    true,
  );
  assert.equal(
    await good.page.evaluate(() => window.arrivalFixture.watches),
    1,
  );
  await good.page
    .getByText("Next attraction: Synthetic second garden", { exact: true })
    .waitFor();
  for (let index = 0; index < 4; index++) {
    await advance(good.page, 15000);
    await good.page.evaluate(() => window.arrivalFixture.send());
  }
  assert.equal(
    good.writes.length,
    1,
    "Stationary fixes must not cascade to another co-located identity",
  );
  await good.page.getByText(/Leave this arrival area/).waitFor();
  await advance(good.page, 15000);
  await good.page.evaluate(() =>
    window.arrivalFixture.send({ latitude: 40.003 }),
  );
  await advance(good.page, 15000);
  await dwell(good.page);
  await good.page.getByText("2 of 2 stops visited", { exact: true }).waitFor();
  await good.page.getByText("Visit updates saved.", { exact: true }).waitFor();
  assert.equal(good.writes.length, 2);
  assert.equal(
    await good.page.evaluate(() => window.arrivalFixture.watches),
    1,
    "Presentation saves and next-target changes must preserve the original watch",
  );
  await good.page
    .getByRole("button", {
      name: "Undo detected visit: Synthetic second garden",
      exact: true,
    })
    .click();
  await good.page.getByText("1 of 2 stops visited", { exact: true }).waitFor();
  await good.page.getByText("Visit updates saved.", { exact: true }).waitFor();
  assert.equal(good.writes.length, 3);
  assert.equal(good.writes[2].presentation.visitedStopIds.length, 1);
  assert.equal(
    await good.page.evaluate(() => window.arrivalFixture.active),
    false,
  );
  for (const width of [390, 1440]) {
    await good.page.setViewportSize({ width, height: 900 });
    assert.ok(
      await good.page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
  }
  await good.page.screenshot({
    path: join(output, "arrival-assist.png"),
    fullPage: true,
  });
  await good.context.close();
  const denied = await fixture();
  await enable(denied.page);
  await denied.page.evaluate(() => window.arrivalFixture.deny());
  await denied.page.getByText(/Location permission was denied/).waitFor();
  assert.equal(denied.writes.length, 0);
  assert.equal(
    await denied.page.evaluate(() => window.arrivalFixture.active),
    false,
  );
  await denied.page
    .getByRole("button", {
      name: "Mark visited: Synthetic arrival garden",
      exact: true,
    })
    .click();
  await denied.page
    .getByText("Visit updates saved.", { exact: true })
    .waitFor();
  assert.equal(denied.writes.length, 1);
  await denied.context.close();
  const stale = await fixture({ conflict: true });
  await enable(stale.page);
  await dwell(stale.page);
  await stale.page.getByText(/This saved trip changed/).waitFor();
  assert.equal(stale.writes.length, 1);
  await advance(stale.page, 15000);
  await stale.page.evaluate(() => window.arrivalFixture.send());
  assert.equal(stale.writes.length, 1);
  assert.equal(
    await stale.page.evaluate(() => window.arrivalFixture.active),
    false,
  );
  await stale.context.close();
  assert.deepEqual(errors, []);
  assert.deepEqual(blocked, []);
  await writeFile(
    join(output, "result.json"),
    JSON.stringify(
      {
        passed: true,
        scope:
          "Actual Chromium UI, mocked geolocation and synthetic identity/intercepted persistence; no real API/database or location provider.",
        successfulWrites: good.writes,
        deniedFallbackWrites: denied.writes.length,
        staleRejectedWrites: stale.writes.length,
        errors,
        blocked,
      },
      null,
      2,
    ) + "\n",
  );
  console.log(
    "PASS: opt-in automatic arrival, guarded dwell, co-located departure/re-entry across actual client revision updates, undo, denied-location manual fallback, stale-save stop, 390/1440 layout. Browser positions and persistence are mocked.",
  );
} finally {
  await browser.close();
}
