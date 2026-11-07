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

async function fixtureReport() {
  return (
    await fetch(backend + "/fixture/report", {
      signal: AbortSignal.timeout(5000),
    })
  ).json();
}

async function api(page, path, options = {}) {
  return page.evaluate(
    async ({ backend, path, options }) => {
      // Synthetic local identity only. Auth values remain inside the page and are
      // never returned, printed, persisted in artifacts, or sent to hosted origins.
      const token = sessionStorage.getItem("accessToken");
      const response = await fetch(backend + path, {
        method: options.method || "GET",
        headers: {
          Authorization: "Bearer " + token,
          "X-Cognito-Id-Token": sessionStorage.getItem("idToken"),
          ...(options.body ? { "Content-Type": "application/json" } : {}),
        },
        ...(options.body
          ? { body: JSON.stringify({ ...options.body, PartitionKey: token }) }
          : {}),
      });
      return { status: response.status, data: await response.json() };
    },
    { backend, path, options },
  );
}

async function assertWidths(page) {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      true,
      `The current page must fit the ${width}px viewport`,
    );
  }
}

function assertReservedMeals(trip) {
  const route = trip.route;
  assert.equal(route.reserve_meal_slots, true);
  const meals = trip.itinerary
    .flatMap((day) => day.stops)
    .filter((stop) => stop.kind === "meal");
  assert.equal(
    meals.length,
    1,
    "This dated short fixture needs exactly one lunch",
  );
  assert.equal(meals[0].name, "Lunch");
  const seconds = (value) => Date.parse(value) / 1000;
  for (const meal of meals) {
    assert.equal(meal.status, "reserved");
    assert.equal(meal.duration_seconds, 2700);
    assert.equal(
      seconds(meal.departure_time) - seconds(meal.arrival_time),
      meal.duration_seconds,
    );
    assert.ok(seconds(meal.arrival_time) >= seconds(meal.window_start));
    assert.ok(seconds(meal.departure_time) <= seconds(meal.window_end));
    assert.ok(
      !meal.provider_id && !meal.coordinates,
      "Meal reservations do not suggest venues",
    );
    for (const stop of route.stops.filter((item) => item.type === "stop")) {
      assert.ok(
        seconds(meal.departure_time) <= seconds(stop.arrival_time) ||
          seconds(meal.arrival_time) >= seconds(stop.departure_time),
        "Meals cannot overlap attraction visits",
      );
    }
  }
  // This fixture has no hotels/opening waits. Driving may pause for a meal;
  // total arrival time must include every drive, physical visit and reservation.
  const drive = route.stops.reduce((sum, stop) => sum + stop.duration, 0);
  const visit = route.stops.reduce(
    (sum, stop) =>
      sum +
      (stop.type === "stop"
        ? seconds(stop.departure_time) - seconds(stop.arrival_time)
        : 0),
    0,
  );
  const reserved = meals.reduce((sum, meal) => sum + meal.duration_seconds, 0);
  const elapsed =
    seconds(route.stops.at(-1).arrival_time) - seconds(route.departure_time);
  assert.ok(
    Math.abs(elapsed - drive - visit - reserved) < 1,
    "Actual arrival must reserve meal time beyond driving and visit durations",
  );
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
  await page.getByRole("link", { name: "Open trip", exact: true }).click();
  await page
    .getByRole("heading", { name: "Trip details", exact: true })
    .waitFor();
  await page
    .getByRole("region", { name: "Meal breaks", exact: true })
    .waitFor();
  const created = await fixtureReport();
  assertReservedMeals(created.trips[0].data);
  assert.equal(
    created.profiles.length,
    1,
    "Saving a trip saves its stated reusable choices",
  );
  await assertWidths(page);
  await page.screenshot({
    path: join(output, "trip-workspace.png"),
    fullPage: true,
  });
  await page
    .getByRole("navigation", { name: "Trip views" })
    .getByRole("link", { name: "Itinerary", exact: true })
    .click();
  await page.getByRole("heading", { name: "Itinerary", exact: true }).waitFor();

  // No reload between create, visit and undo: each actual response must refresh
  // the modern snapshot revision, including the exposed create response header.
  const original = await api(page, "/chats");
  assert.equal(original.status, 200);
  const [oldData, oldLog] = original.data[0];
  assert.match(oldData.savedRevision, /^[0-9a-f]{64}$/);
  const mark = page
    .getByRole("button", { name: /^Mark visited: Synthetic overlook / })
    .first();
  const visitedName = (await mark.getAttribute("aria-label")).replace(
    "Mark visited: ",
    "",
  );
  await mark.click();
  await page.getByText("Visit updates saved.", { exact: true }).waitFor();
  const afterVisit = await fixtureReport();
  assert.equal(afterVisit.trips[0].data.presentation.visitedStopIds.length, 1);
  const visited = await api(page, "/chats");
  assert.notEqual(visited.data[0][0].savedRevision, oldData.savedRevision);
  const stale = await api(page, `/chats/update/${oldData.chatId}`, {
    method: "PUT",
    body: {
      ChatData: oldData,
      ChatLog: oldLog,
      ExpectedRevision: oldData.savedRevision,
      UpdateScope: "presentation",
    },
  });
  assert.equal(
    stale.status,
    409,
    "Real stale CAS must reject an old presentation snapshot",
  );
  assert.deepEqual(
    (await fixtureReport()).trips,
    afterVisit.trips,
    "A rejected stale save must preserve the durable trip",
  );
  await page
    .getByRole("button", { name: "Undo visited: " + visitedName, exact: true })
    .click();
  await page.getByText("Visit updates saved.", { exact: true }).waitFor();
  const undone = await api(page, "/chats");
  assert.notEqual(
    undone.data[0][0].savedRevision,
    visited.data[0][0].savedRevision,
  );
  assert.deepEqual(
    (await fixtureReport()).trips[0].data.presentation.visitedStopIds,
    [],
  );
  await page.goto(frontend + "/trips");
  await page
    .getByRole("heading", { name: "Saved trips", exact: true })
    .waitFor();
  await page
    .getByRole("link", { name: "Open trip", exact: true })
    .first()
    .click();
  await page.reload();
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

  // Browse and edit use actual HTTP routes/current-fact validation and timing.
  // Only the source facts and roads are synthetic external-provider boundaries.
  await page
    .getByRole("navigation", { name: "Trip views" })
    .getByRole("link", { name: "Edit itinerary", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Edit itinerary", exact: true })
    .waitFor();
  const beforePreview = await fixtureReport();
  await page.getByRole("button", { name: "Find places", exact: true }).click();
  await page
    .getByRole("button", { name: "Choose Synthetic edit stop", exact: true })
    .click();
  await page.getByRole("combobox", { name: /^Action/ }).selectOption("replace");
  await page.getByRole("combobox", { name: /^Replace/ }).selectOption("0");
  await page
    .getByRole("button", { name: "Recalculate trip", exact: true })
    .click();
  await Promise.race([
    page
      .getByRole("heading", { name: "Review changes", exact: true })
      .waitFor({ timeout: 30000 }),
    page
      .getByRole("alert")
      .waitFor({ timeout: 30000 })
      .then(async () => {
        throw Error(
          "Route edit failed: " + (await page.getByRole("alert").innerText()),
        );
      }),
  ]);
  assert.deepEqual(
    (await fixtureReport()).trips,
    beforePreview.trips,
    "Reviewing an edit must not persist it",
  );
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await page.getByText("Trip changes saved.", { exact: true }).waitFor();
  const edited = await fixtureReport();
  assert.equal(
    edited.trips[0].data.route.stops[0].provider_id,
    "overture:guided-edit",
  );
  assertReservedMeals(edited.trips[0].data);
  assert.deepEqual(edited.trips[0].data.presentation.visitedStopIds, []);
  await page.getByRole("link", { name: "Back to trip", exact: true }).click();
  await page.reload();
  const editedMark = page.getByRole("button", {
    name: "Mark visited: Synthetic edit stop",
    exact: true,
  });
  await editedMark.waitFor();
  await editedMark.click();
  await page.getByText("Visit updates saved.", { exact: true }).waitFor();
  await page
    .getByRole("button", {
      name: "Undo visited: Synthetic edit stop",
      exact: true,
    })
    .click();
  await page.getByText("Visit updates saved.", { exact: true }).waitFor();
  await page.reload();
  await editedMark.waitFor();
  await page.screenshot({
    path: join(output, "reloaded-edited-trip.png"),
    fullPage: true,
  });
  await assertWidths(page);

  await page.goto(frontend + "/settings");
  await page.getByRole("heading", { name: "Settings", exact: true }).waitFor();
  await page
    .getByRole("button", { name: "New preferences", exact: true })
    .click();
  await page
    .getByLabel("Profile name", { exact: true })
    .fill("Synthetic weekend");
  await page
    .getByLabel("Start driving each morning", { exact: true })
    .fill("08:30");
  await page
    .getByRole("button", { name: "Save preferences", exact: true })
    .click();
  await page.getByText("Preferences saved.", { exact: true }).waitFor();
  await page.reload();
  await page
    .getByRole("button", { name: "Edit Synthetic weekend", exact: true })
    .click();
  assert.equal(
    await page
      .getByLabel("Start driving each morning", { exact: true })
      .inputValue(),
    "08:30",
  );
  await page
    .getByLabel("Profile name", { exact: true })
    .fill("Synthetic weekend updated");
  await page
    .getByRole("button", { name: "Save preferences", exact: true })
    .click();
  await page.getByText("Preferences saved.", { exact: true }).waitFor();
  await page.reload();
  await page
    .getByRole("heading", { name: "Synthetic weekend updated", exact: true })
    .waitFor();
  const beforeCar = await fixtureReport();
  const carRegion = page.getByRole("region", { name: "Trip car", exact: true });
  await carRegion
    .getByRole("radio", { name: "Use this car", exact: true })
    .check();
  await carRegion.getByLabel("Car year", { exact: true }).fill("2020");
  await carRegion.getByLabel("Car make", { exact: true }).fill("Synthetic");
  await carRegion.getByLabel("Car model", { exact: true }).fill("Tourer");
  await carRegion
    .getByRole("button", { name: "Save trip car", exact: true })
    .click();
  await page.getByText("Trip car saved.", { exact: true }).waitFor();
  await page.reload();
  await carRegion.getByLabel("Car model", { exact: true }).waitFor();
  assert.equal(
    await carRegion.getByLabel("Car model", { exact: true }).inputValue(),
    "Tourer",
  );
  const afterCar = await fixtureReport();
  assert.deepEqual(afterCar.trips[0].data.carDetails, [
    "2020",
    "Synthetic",
    "Tourer",
  ]);
  for (const key of ["route", "itinerary", "presentation"])
    assert.deepEqual(afterCar.trips[0].data[key], beforeCar.trips[0].data[key]);
  assert.deepEqual(
    afterCar.profiles,
    beforeCar.profiles,
    "Trip-specific car changes must not overwrite reusable profiles",
  );
  assert.equal(afterCar.profiles.length, 2);
  const profile = afterCar.profiles.find(
    (item) => item.name === "Synthetic weekend updated",
  );
  assert.equal(profile.choices.scheduling_policy.morning_restart, "08:30");
  assert.deepEqual(Object.keys(profile.choices).sort(), [
    "car",
    "car_status",
    "persona_weights",
    "scheduling_policy",
  ]);
  assert.equal(Object.keys(profile.choices.persona_weights).length, 14);
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
  await assertWidths(page);
  await page.goto(frontend + "/plan");
  for (let step = 0; step < 4; step++)
    await page.getByRole("button", { name: "Back", exact: true }).click();
  await page
    .getByLabel("Saved preferences", { exact: true })
    .selectOption(profile.id);
  await page
    .getByRole("button", { name: "Load preferences", exact: true })
    .click();
  await page
    .getByText(
      "Preferences loaded. Your trip locations, date and stops are unchanged.",
      { exact: true },
    )
    .waitFor();
  for (let step = 0; step < 3; step++)
    await page.getByRole("button", { name: "Next", exact: true }).click();
  assert.equal(
    await page
      .getByLabel("Start driving next morning", { exact: true })
      .inputValue(),
    "08:30",
  );
  await page.goto(frontend + "/trip");
  await page.reload();
  await page
    .getByRole("button", {
      name: "Mark visited: Synthetic edit stop",
      exact: true,
    })
    .waitFor();
  const happyReport = await (await fetch(backend + "/fixture/report")).json();
  assert.equal(happyReport.stored_trips, 1);
  assert.equal(happyReport.solver, 1);
  assert.ok(happyReport.browse > 0 && happyReport.current_facts > 0);
  assertReservedMeals(happyReport.trips[0].data);
  await writeFile(
    join(output, "happy-result.json"),
    JSON.stringify({ passed: true, report: happyReport }, null, 2) + "\n",
  );
  console.log(
    "PASS: actual trip creation, reserved meals, sequential visit revisions, stale rejection, edit preview/save/reload and Settings profile/car persistence in disposable PostgreSQL.",
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
