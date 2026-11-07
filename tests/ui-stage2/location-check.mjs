// Ambiguous locations use deterministic intercepted replies, never geocoding.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
const tools =
  process.env.UI_BROWSER_TOOLS_DIR ||
  join(import.meta.dirname, "../guidedjourney");
const { chromium } = await import(
  pathToFileURL(join(tools, "node_modules/playwright-core/index.mjs"))
);
const frontend = "http://127.0.0.1:5187",
  backend = "http://127.0.0.1:18999";
const out =
  process.env.ROADTRIPS_UI_EVIDENCE_DIR ||
  "/tmp/roadtrips-ui-location-evidence";
await mkdir(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  headless: true,
  args: ["--no-sandbox", "--disable-background-networking"],
});
const audits = [],
  errors = [],
  blocked = [],
  roadRequests = [];
const origins = [
  { address: "Boulder, Colorado", latitude: 40, longitude: -105 },
  { address: "Boulder, Wyoming", latitude: 42, longitude: -109 },
];
const destinations = [
  { address: "Denver, Colorado", latitude: 39, longitude: -104 },
  { address: "Denver, Pennsylvania", latitude: 40, longitude: -76 },
];
let completed = false;
try {
  for (const [width, height] of [
    [390, 844],
    [375, 812],
    [1440, 900],
  ]) {
    const context = await browser.newContext({
      viewport: { width, height },
      reducedMotion: "reduce",
    });
    await context.addInitScript(() => {
      for (const use of ["access", "id"])
        sessionStorage.setItem(
          use + "Token",
          "header." +
            btoa(
              JSON.stringify({
                iss: "fixture",
                sub: "ui-ambiguity",
                token_use: use,
                exp: Date.now() / 1000 + 3600,
              }),
            ) +
            ".fixture",
        );
    });
    await context.route("**/*", async (route) => {
      const url = new URL(route.request().url());
      if (url.origin === frontend) return route.continue();
      if (url.origin !== backend) {
        blocked.push(url.origin);
        return route.abort();
      }
      if (["/chats", "/preference-profiles"].includes(url.pathname))
        return route.fulfill({ json: [] });
      if (url.pathname === "/validate-location")
        return route.fulfill({
          status: 409,
          json: {
            detail: {
              candidates:
                JSON.parse(route.request().postData()).location.address ===
                "Boulder"
                  ? origins
                  : destinations,
            },
          },
        });
      if (url.pathname === "/get-initial-route") {
        roadRequests.push(Object.fromEntries(url.searchParams));
        return route.fulfill({
          json: {
            duration: 7200,
            distance: 150000,
            geometry: {
              type: "LineString",
              coordinates: [
                [-109, 42],
                [-76, 40],
              ],
            },
          },
        });
      }
      if (url.pathname === "/route-preparation/stream")
        return route.fulfill({
          contentType: "application/x-ndjson",
          headers: { "access-control-allow-origin": frontend },
          body:
            JSON.stringify({
              type: "result",
              response: {
                catalog_status: "ready",
                places: [],
                possible_overnight_areas: [],
                sections_checked: 6,
              },
            }) + "\n",
        });
      throw Error("Unexpected ambiguity fixture API: " + url.pathname);
    });
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(frontend + "/plan");
    await page
      .getByLabel("Starting city or address", { exact: true })
      .fill("Boulder");
    await page.getByLabel("Destination", { exact: true }).fill("Denver");
    await page.getByLabel("Departure date", { exact: true }).fill("2027-06-01");
    await page
      .getByRole("button", { name: "Estimate driving time", exact: true })
      .click();
    const confirm = page.getByRole("button", {
      name: "Use these locations for estimate",
      exact: true,
    });
    await page
      .getByRole("radio", { name: "Denver, Pennsylvania", exact: true })
      .waitFor();
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    const metrics = await page.evaluate(() => ({
      width: innerWidth,
      height: innerHeight,
      scrollWidth: document.documentElement.scrollWidth,
      scrollHeight: document.documentElement.scrollHeight,
      scrollContainers: [...document.querySelectorAll("*")]
        .filter(
          (n) =>
            n.getClientRects().length &&
            /auto|scroll/.test(getComputedStyle(n).overflowY) &&
            n.scrollHeight > n.clientHeight + 2,
        )
        .map((n) => n.className),
    }));
    const name = `locations-${width}x${height}`;
    audits.push({ name, ...metrics });
    await page.screenshot({ path: join(out, name + ".png"), fullPage: true });
    assert.equal(
      await page.getByRole("radio").count(),
      4,
      "two genuine matches per endpoint",
    );
    await page
      .getByRole("radio", { name: "Boulder, Wyoming", exact: true })
      .check();
    await page
      .getByRole("radio", { name: "Denver, Pennsylvania", exact: true })
      .check();
    await confirm.click();
    await page.getByText(/View route · About/).waitFor();
    assert.equal(
      await page
        .getByLabel("Starting city or address", { exact: true })
        .inputValue(),
      "Boulder",
    );
    assert.equal(
      await page.getByLabel("Destination", { exact: true }).inputValue(),
      "Denver",
    );
    assert.equal(
      await page.getByLabel("Departure date", { exact: true }).inputValue(),
      "2027-06-01",
    );
    assert.deepEqual(
      roadRequests.at(-1),
      { start_lat: "42", start_lon: "-109", end_lat: "40", end_lon: "-76" },
      "route uses explicitly selected coordinates",
    );
    await context.close();
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(blocked, []);
  assert.equal(roadRequests.length, 3);
  for (const a of audits) {
    assert.ok(a.scrollWidth <= a.width, a.name + " horizontal overflow");
    assert.ok(a.scrollHeight <= a.height + 2, a.name + " document scrolling");
    assert.deepEqual(a.scrollContainers, [], a.name + " nested scrolling");
  }
  completed = true;
  console.log(
    JSON.stringify({
      passed: true,
      screens: audits.length,
      errors,
      blocked,
      out,
    }),
  );
} finally {
  await writeFile(
    join(out, "location-report.json"),
    JSON.stringify(
      {
        scope:
          "Actual location-choice UI with intercepted deterministic geocoding/roads; no provider calls",
        passed: completed,
        audits,
        errors,
        blocked,
        roadRequests,
      },
      null,
      2,
    ),
  );
  await browser.close();
}
