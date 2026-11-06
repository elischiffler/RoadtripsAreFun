import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { chromium } from "playwright-core";

const frontend = "http://127.0.0.1:8082";
const backend = "http://127.0.0.1:8002";
const output =
  process.env.GUIDED_JOURNEY_ARTIFACTS ||
  join(import.meta.dirname, ".artifacts");
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/google-chrome",
  headless: true,
  args: [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-background-networking",
  ],
});
const errors = [],
  blocked = [],
  http = [];
let activePage;

async function session() {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (![frontend, backend, "http://127.0.0.1:8999"].includes(url.origin)) {
      blocked.push(url.origin);
      return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage();
  activePage = page;
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (url.origin !== backend) return;
    http.push({ path: url.pathname, status: response.status() });
  });
  await page.goto(frontend + "/login");
  await page
    .getByRole("textbox", { name: /^Email/ })
    .fill("traveler@example.test");
  await page.getByLabel(/^Password/).fill("fixture-only");
  await page.getByRole("button", { name: "Log In", exact: true }).click();
  await page.waitForURL(frontend + "/");
  return { context, page };
}

async function enterTrip(page, date) {
  await page.goto(frontend + "/plan");
  await page
    .getByLabel("Starting city or address", { exact: true })
    .fill("Boulder");
  await page.getByLabel("Destination", { exact: true }).fill("Fort Morgan");
  await page.getByLabel("Departure date", { exact: true }).fill(date);
  await page.getByLabel("Departure time", { exact: true }).fill("09:00");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page
    .getByLabel("Would you like to add your car?", { exact: true })
    .selectOption("skipped");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page
    .getByRole("button", { name: "Check locations", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Confirm your locations", exact: true })
    .waitFor();
  await page
    .getByRole("button", {
      name: "Confirm locations and plan route",
      exact: true,
    })
    .click();
}

try {
  const { context, page } = await session();
  const future = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10);
  await enterTrip(page, future);
  await Promise.race([
    page.getByText("Trip saved.", { exact: true }).waitFor({ timeout: 60000 }),
    page
      .getByRole("alert")
      .waitFor({ timeout: 60000 })
      .then(async () => {
        throw Error(
          "Trip creation failed: " +
            (await page.getByRole("alert").innerText()),
        );
      }),
  ]);
  await page
    .getByRole("link", { name: "View itinerary", exact: true })
    .waitFor();
  assert.equal(
    await page
      .getByRole("progressbar", {
        name: "Trip planning milestones",
        exact: true,
      })
      .evaluate((element) => element.value === 100 && element.max === 100),
    true,
  );
  await page.screenshot({
    path: join(output, "saved-trip.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "View itinerary", exact: true }).click();
  await page
    .getByText(/^Synthetic overlook /)
    .first()
    .waitFor();
  await page.reload();
  await page
    .getByText(/^Synthetic overlook /)
    .first()
    .waitFor();
  const mark = page
    .getByRole("button", { name: /^Mark visited: Synthetic overlook / })
    .first();
  const visitedName = (await mark.getAttribute("aria-label")).replace(
    "Mark visited: ",
    "",
  );
  await mark.click();
  await page
    .getByRole("button", { name: /^Undo visited: Synthetic overlook / })
    .waitFor();
  await page.getByText("Visit updates saved.", { exact: true }).waitFor();
  await page.reload();
  await page
    .getByRole("button", { name: /^Undo visited: Synthetic overlook / })
    .waitFor();
  await page
    .getByRole("button", { name: /^Undo visited: Synthetic overlook / })
    .click();
  await page
    .getByRole("button", { name: /^Undo visited: Synthetic overlook / })
    .waitFor({ state: "detached" });
  await page.getByText("Visit updates saved.", { exact: true }).waitFor();
  await page.goto(frontend + "/trips");
  await page
    .getByRole("heading", { name: "Saved trips", exact: true })
    .waitFor();
  await page
    .getByRole("link", { name: "View itinerary", exact: true })
    .first()
    .click();
  await page
    .getByText(/^Synthetic overlook /)
    .first()
    .waitFor();
  await page
    .getByRole("button", { name: "Mark visited: " + visitedName, exact: true })
    .waitFor();
  assert.equal(
    await page
      .getByRole("button", {
        name: "Undo visited: " + visitedName,
        exact: true,
      })
      .count(),
    0,
  );
  await page.screenshot({
    path: join(output, "reloaded-itinerary.png"),
    fullPage: true,
  });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  await page.goto(frontend + "/settings");
  await page.getByRole("heading", { name: "Settings", exact: true }).waitFor();
  assert.equal(
    await page
      .getByRole("link", { name: /^(AI Studio|Trip research)/ })
      .count(),
    0,
  );
  const researchStatus = await page.evaluate(async (api) => {
    // These are this disposable fixture's synthetic tokens. Return only status;
    // never export headers or browser authentication state into evidence.
    const response = await fetch(api + "/studio/presets", {
      headers: {
        Authorization: "Bearer " + sessionStorage.getItem("accessToken"),
        "X-Cognito-Id-Token": sessionStorage.getItem("idToken"),
      },
    });
    return response.status;
  }, backend);
  assert.equal(
    researchStatus,
    403,
    "The actual API must reject verified non-owner research access",
  );
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      true,
    );
  }
  await page.goto(frontend + "/itinerary");
  await page.reload();
  await page
    .getByRole("button", { name: "Mark visited: " + visitedName, exact: true })
    .waitFor();
  const happyReport = await (await fetch(backend + "/fixture/report")).json();
  assert.equal(happyReport.stored_trips, 1);
  assert.equal(happyReport.solver, 1);
  await writeFile(
    join(output, "happy-result.json"),
    JSON.stringify({ passed: true, report: happyReport }, null, 2) + "\n",
  );
  console.log(
    "PASS: future trip created through actual HTTP/API/CP-SAT and persisted/reloaded/visited/undone in disposable PostgreSQL.",
  );
  await context.close();

  const failed = await session();
  await enterTrip(failed.page, "2000-01-01");
  const alert = failed.page.getByRole("alert");
  await alert.waitFor();
  const departureError = await alert.innerText();
  assert.equal(
    await failed.page.getByText("Trip saved.", { exact: true }).count(),
    0,
  );
  assert.equal(
    await failed.page
      .getByRole("link", { name: "View itinerary", exact: true })
      .count(),
    0,
  );
  const progressbar = failed.page.getByRole("progressbar", {
    name: "Trip planning milestones",
    exact: true,
  });
  assert.equal(await progressbar.count(), 1);
  assert.ok(
    await progressbar.evaluate(
      (element) => element.max === 100 && element.value < 100,
    ),
  );
  await failed.context.close();
  const report = await (await fetch(backend + "/fixture/report")).json();
  assert.equal(report.login, 2);
  assert.ok(
    report.catalog > 0 &&
      report.ratings > 0 &&
      report.durations > 0 &&
      report.gateway_auth > 0,
  );
  assert.equal(
    report.solver,
    1,
    "Only the valid trip may execute the actual CP-SAT selection",
  );
  assert.equal(
    report.stored_trips,
    1,
    "The failed trip must not create a database row",
  );
  assert.deepEqual(
    report.blocked_network,
    [],
    "An unexpected provider connection must fail the gate",
  );
  assert.equal(
    report.requests.filter((r) => r.path === "/generate-final-route/stream")
      .length,
    2,
  );
  assert.equal(
    report.stream_events.filter((event) => event.type === "result").length,
    1,
  );
  assert.equal(
    report.stream_events.filter((event) => event.type === "error").length,
    1,
  );
  assert.deepEqual(
    report.stream_events.filter((event) => event.type === "error"),
    [{ type: "error", status: 422, code: "departure_not_upcoming" }],
  );
  assert.deepEqual(blocked, []);
  assert.deepEqual(errors, []);
  assert.equal(
    departureError,
    "Choose a departure date and time in the future.",
    "An expired departure must explain the real rejection rather than hide its reason",
  );
  await writeFile(
    join(output, "result.json"),
    JSON.stringify(
      {
        scope:
          "Actual browser, HTTP FastAPI, signed synthetic JWT verifier, CP-SAT, actual-leg timing, itinerary and disposable PostgreSQL; synthetic catalog/geocoding/road/gateway providers.",
        passed: true,
        report,
        http,
        errors,
        blocked,
      },
      null,
      2,
    ) + "\n",
  );
  console.log(
    "PASS: signed offline guided trip created, persisted, reloaded and visited; expired trip rejected without saving.",
  );
} catch (error) {
  if (activePage && !activePage.isClosed()) {
    await activePage
      .screenshot({
        path: join(output, "failure.png"),
        fullPage: true,
        timeout: 5000,
      })
      .catch(() => {});
    console.error(
      "Visible fixture page:",
      (await activePage.locator("body").innerText()).slice(0, 5000),
    );
  }
  console.error(JSON.stringify({ errors, blocked, http }));
  const report = await fetch(backend + "/fixture/report", {
    signal: AbortSignal.timeout(5000),
  })
    .then((response) => response.json())
    .catch(() => null);
  await writeFile(
    join(output, "failure.json"),
    JSON.stringify(
      { passed: false, error: error.message, report, errors, blocked, http },
      null,
      2,
    ) + "\n",
  );
  throw error;
} finally {
  await browser.close();
}
