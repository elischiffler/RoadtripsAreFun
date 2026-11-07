import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { chromium } from "playwright-core";
import { runOvernightJourney } from "./overnight.mjs";

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

async function session({
  email = "traveler@example.test",
  homePath = "/plan",
} = {}) {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  await context.exposeBinding("rejectRealLocation", () =>
    blocked.push("device-geolocation"),
  );
  await context.addInitScript(() => {
    // The main release journey uses explicit manual corrections. Real device
    // acquisition is forbidden here; automatic arrivals have a separate mocked
    // position harness. A caught unexpected call still fails the release gate.
    const denyLocation = () => {
      void window.rejectRealLocation();
      throw new Error("Offline release journey prohibits device geolocation");
    };
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        getCurrentPosition: denyLocation,
        watchPosition: denyLocation,
        clearWatch: () => {},
      },
    });
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
  await page.getByRole("textbox", { name: /^Email/ }).fill(email);
  await page.getByLabel(/^Password/).fill("fixture-only");
  await page.getByRole("button", { name: "Log In", exact: true }).click();
  // Await the real Home decision rather than its transient '/' redirect.
  await page.waitForURL(frontend + homePath);
  return { context, page };
}

let expectedSolverCalls = 1;
let expectedWorkCounters;
const counterKeys = [
  "ratings",
  "durations",
  "gateway_requests",
  "catalog",
  "solver",
  "hotel_requests",
];
const workCounters = (report) =>
  Object.fromEntries(counterKeys.map((key) => [key, report[key]]));
const ordinarySetupFits = [];
async function assertOrdinarySetupFit(page, group, action = "Next") {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".setup-section").waitFor({ state: "visible" });
  const next = page.getByRole("button", { name: action, exact: true });
  await next.waitFor({ state: "visible" });
  // Observe settled layout without scrolling a control into view. Expanded
  // reviews, errors, small screens and large-text fallbacks are separate cases.
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  const fit = await next.evaluate((button) => {
    const section = document.querySelector(".setup-section");
    const bounds = button.getBoundingClientRect();
    return {
      width: innerWidth,
      height: innerHeight,
      documentHeight: Math.max(
        document.documentElement.scrollHeight,
        document.body.scrollHeight,
      ),
      sectionHeight: section.clientHeight,
      sectionScrollHeight: section.scrollHeight,
      nextTop: bounds.top,
      nextBottom: bounds.bottom,
      nextLeft: bounds.left,
      nextRight: bounds.right,
      routeOpen: Boolean(document.querySelector(".setup-route-map[open]")),
    };
  });
  assert.equal(
    fit.routeOpen,
    false,
    `${group}: close the optional route review before checking fit`,
  );
  assert.ok(
    fit.documentHeight <= fit.height + 1,
    `${group}: ordinary page needs vertical scrolling: ${JSON.stringify(fit)}`,
  );
  assert.ok(
    fit.sectionScrollHeight <= fit.sectionHeight + 1,
    `${group}: questions overflow their own panel: ${JSON.stringify(fit)}`,
  );
  assert.ok(
    fit.nextTop >= 0 &&
      fit.nextBottom <= fit.height + 1 &&
      fit.nextLeft >= 0 &&
      fit.nextRight <= fit.width + 1,
    `${group}: the next action must be visible without scrolling: ${JSON.stringify(fit)}`,
  );
  ordinarySetupFits.push({ group, action, ...fit });
}
async function enterTrip(page, date, { expectFailure = false } = {}) {
  const before = await fixtureReport();
  await page.goto(frontend + "/plan");
  await page
    .getByLabel("Starting city or address", { exact: true })
    .fill("Boulder");
  await page.getByLabel("Destination", { exact: true }).fill("Fort Morgan");
  await page.getByLabel("Departure date", { exact: true }).fill(date);
  await page.getByLabel("Departure time", { exact: true }).fill("09:00");
  for (let step = 0; step < 4; step++) {
    if (step === 1)
      await page
        .getByLabel("How many attractions would you like?", { exact: true })
        .fill("3");
    await assertOrdinarySetupFit(
      page,
      `primary ${expectFailure ? "expired" : "future"} group ${step}`,
    );
    await page.getByRole("button", { name: "Next", exact: true }).click();
  }
  await assertOrdinarySetupFit(
    page,
    `primary ${expectFailure ? "expired" : "future"} review`,
    "Check trip options",
  );
  const prepared = await fixtureReport();
  assert.deepEqual(
    workCounters(prepared),
    workCounters(before),
    "Preparing locations, roads and grouped answers must not start AI or scheduling",
  );
  assert.equal(prepared.stored_trips, before.stored_trips);
  const actualRequest = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      new URL(request.url()).pathname === "/planning-candidates/stream",
  );
  await page
    .getByRole("button", { name: "Check trip options", exact: true })
    .click();
  const payload = (await actualRequest).postDataJSON();
  assert.match(payload.request_id, /^[0-9a-f-]{36}$/i);
  assert.equal(payload.num_stops, 3);
  assert.equal(Object.hasOwn(payload, "budget"), false);
  assert.equal(Object.hasOwn(payload, "hotel_rooms"), false);
  assert.equal(payload.reserve_meal_slots, true);
  assert.equal(payload.scheduling_policy.daily_schedule.slots.length, 24);
  if (expectFailure) return { payload };
  await Promise.race([
    page
      .getByRole("button", { name: "Finish in one day", exact: true })
      .waitFor({ timeout: 60000 }),
    page
      .getByRole("alert")
      .waitFor({ timeout: 60000 })
      .then(async () => {
        throw Error(
          "Candidate assessment failed: " +
            (await page.getByRole("alert").innerText()),
        );
      }),
  ]);
  await page
    .getByRole("img", { name: "Trip option route geometry", exact: true })
    .waitFor();
  const assessed = await fixtureReport();
  assert.equal(
    assessed.stored_trips,
    0,
    "Successful assessment must remain unsaved before explicit mode confirmation",
  );
  assert.equal(await page.getByText("Trip saved.", { exact: true }).count(), 0);
  const progress = page.getByRole("progressbar", {
    name: "Trip planning milestones",
    exact: true,
  });
  assert.equal(await progress.count(), 1);
  assert.ok(
    await progress.evaluate(
      (element) => element.max === 100 && element.value < 100,
    ),
    "A checked but unconfirmed candidate must not signal completion",
  );
  assert.equal(
    assessed.hotel_requests,
    0,
    "One-day assessment must never query hotels",
  );
  assert.equal(
    assessed.solver,
    1,
    "The primary complete candidate must run the real solver",
  );
  // Actual duplicate HTTP assessment reuses the registered server-owned result.
  // No response/proof is constructed in this fixture or browser.
  const cached = await api(page, "/planning-candidates", {
    method: "POST",
    body: payload,
  });
  assert.equal(cached.status, 200);
  assert.equal(cached.data.one_day.eligible, true);
  assert.equal(cached.data.one_day.threshold_seconds, 43200);
  assert.ok(cached.data.one_day.elapsed_seconds < 43200);
  assertOneDay(cached.data.candidate_route);
  assert.deepEqual(
    workCounters(await fixtureReport()),
    workCounters(assessed),
    "A same-UUID cached assessment must not replay discovery/models/solver",
  );
  await page
    .getByRole("button", { name: "Finish in one day", exact: true })
    .click();
  return { payload, candidate: cached.data };
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
          ? {
              body: JSON.stringify(
                path.startsWith("/chats/update/")
                  ? { ...options.body, PartitionKey: token }
                  : options.body,
              ),
            }
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

async function sharedOnlyHomeChecks(ownerPage) {
  const before = await fixtureReport();
  await ownerPage.goto(frontend + "/");
  await ownerPage.waitForURL(frontend + "/trips");
  await ownerPage
    .getByRole("heading", { name: "Saved trips", exact: true })
    .waitFor();
  const owned = await api(ownerPage, "/chats");
  assert.equal(owned.status, 200);
  const saved = owned.data[0][0];
  const link = await api(ownerPage, `/chats/${saved.chatId}/sharing/link`, {
    method: "POST",
    body: { expected_revision: saved.savedRevision },
  });
  assert.equal(link.status, 200);
  assert.equal(typeof link.data.token, "string");
  // Keep the capability only in memory, never in a URL, log or artifact.
  const participant = await session({ email: "participant@example.test" });
  const empty = await api(participant.page, "/chats");
  assert.equal(empty.status, 200);
  assert.deepEqual(empty.data, []);
  const connected = await api(participant.page, "/trip-sharing/connect", {
    method: "POST",
    body: { token: link.data.token, display_name: "Synthetic participant" },
  });
  assert.equal(connected.status, 200);
  await participant.page.goto(frontend + "/");
  await participant.page.waitForURL(frontend + "/shared-trips");
  await participant.page
    .getByRole("heading", { name: "Shared with me", exact: true })
    .waitFor();
  await participant.page
    .getByRole("link", { name: "View shared trip", exact: true })
    .click();
  const projection = await api(
    participant.page,
    `/shared-trips/${connected.data.share_id}`,
  );
  assert.equal(projection.status, 200);
  await participant.page
    .getByRole("heading", { name: projection.data.title, exact: true })
    .waitFor();
  await participant.page
    .getByRole("img", { name: "Shared route outline", exact: true })
    .waitFor();
  for (const field of ["presentation", "tripProfile", "ChatLog", "carDetails"])
    assert.equal(Object.hasOwn(projection.data, field), false);
  assert.equal(
    await participant.page
      .getByRole("button", {
        name: /^(Start arrival|Correct an arrival|Mark visited)/,
      })
      .count(),
    0,
  );
  await assertWidths(participant.page);
  const after = await fixtureReport();
  assert.equal(after.participant_owned_trips, 0);
  assert.deepEqual(after.trips, before.trips);
  assert.deepEqual(workCounters(after), workCounters(before));
  await writeFile(
    join(output, "home-entry-result.json"),
    JSON.stringify(
      {
        passed: true,
        emptyOwnerHome: "/plan",
        savedOwnerHome: "/trips",
        sharedOnlyHome: "/shared-trips",
        participantOwnedTrips: after.participant_owned_trips,
        modelWorkUnchanged: true,
      },
      null,
      2,
    ) + "\n",
  );
  await participant.context.close();
  activePage = ownerPage;
}

function assertOneDay(route) {
  assert.equal(route.trip_mode, "one_day");
  assert.equal(route.reserve_meal_slots, true);
  assert.equal(
    route.stops.some((stop) => stop.type === "hotel"),
    false,
  );
  const elapsed =
    (Date.parse(route.stops.at(-1).departure_time) -
      Date.parse(route.departure_time)) /
    1000;
  assert.ok(Number.isFinite(elapsed) && elapsed >= 0 && elapsed < 43200);
  assert.equal(route.one_day_proof.status, "validated");
  assert.equal(route.one_day_proof.threshold_seconds, 43200);
  assert.ok(Math.abs(route.one_day_proof.elapsed_seconds - elapsed) < 1);
  assert.ok(Number.isFinite(Date.parse(route.one_day_proof.validated_at)));
}
async function candidateCacheAndFlexibleChecks(page, assessment) {
  const before = await fixtureReport();
  assert.equal(before.stored_trips, 1);
  const confirmBody = {
    input_key: assessment.candidate.input_key,
    trip_mode: "one_day",
    traveler_count: assessment.payload.traveler_count,
  };
  const duplicate = await api(
    page,
    `/planning-candidates/${assessment.candidate.candidate_id}/confirm`,
    { method: "POST", body: confirmBody },
  );
  assert.equal(duplicate.status, 200);
  assertOneDay(duplicate.data);
  assert.deepEqual(
    workCounters(await fixtureReport()),
    workCounters(before),
    "Identical confirmation must return its cached route without model replay",
  );
  const cancelled = await api(
    page,
    `/planning-candidates/requests/${assessment.payload.request_id}`,
    { method: "DELETE" },
  );
  assert.equal(cancelled.status, 200);
  const cancelledConfirm = await api(
    page,
    `/planning-candidates/${assessment.candidate.candidate_id}/confirm`,
    { method: "POST", body: confirmBody },
  );
  assert.equal(cancelledConfirm.status, 410);
  assert.deepEqual(
    workCounters(await fixtureReport()),
    workCounters(before),
    "A cancelled candidate must fail without repeating AI or solver work",
  );

  // Separate actual HTTP acceptance: flexible stays require occupancy, yet may
  // finish with no hotel. This does not claim a real multi-day/hotel journey.
  const requestId = await page.evaluate(() => crypto.randomUUID());
  const registered = await api(page, "/planning-candidates/requests", {
    method: "POST",
    body: { request_id: requestId },
  });
  assert.equal(registered.status, 200);
  const checked = await api(page, "/planning-candidates", {
    method: "POST",
    body: { ...assessment.payload, request_id: requestId },
  });
  assert.equal(checked.status, 200);
  const afterAssessment = await fixtureReport();
  assert.equal(
    afterAssessment.stored_trips,
    1,
    "A second HTTP assessment must not save another trip",
  );
  const flexible = {
    input_key: checked.data.input_key,
    trip_mode: "overnight",
  };
  const missingOccupancy = await api(
    page,
    `/planning-candidates/${checked.data.candidate_id}/confirm`,
    { method: "POST", body: flexible },
  );
  assert.equal(missingOccupancy.status, 422);
  assert.deepEqual(
    workCounters(await fixtureReport()),
    workCounters(afterAssessment),
  );
  const confirmed = await api(
    page,
    `/planning-candidates/${checked.data.candidate_id}/confirm`,
    {
      method: "POST",
      body: {
        ...flexible,
        traveler_count: 1,
        hotel_rooms: [{ adults: 1, child_ages: [] }],
        budget: 150,
      },
    },
  );
  assert.equal(confirmed.status, 200);
  assert.equal(confirmed.data.trip_mode, "overnight");
  assert.equal(
    confirmed.data.stops.some((stop) => stop.type === "hotel"),
    false,
  );
  const itinerary = await api(page, "/generate-itinerary", {
    method: "POST",
    body: { route: confirmed.data, include_meal_slots: true },
  });
  assert.equal(itinerary.status, 200);
  assertReservedMeals({ route: confirmed.data, itinerary: itinerary.data });
  const after = await fixtureReport();
  for (const key of ["ratings", "durations", "catalog", "gateway_requests"])
    assert.equal(
      after[key],
      afterAssessment[key],
      "Flexible confirmation reuses the checked attraction pool without new AI",
    );
  assert.equal(after.hotel_requests, 0);
  assert.equal(after.stored_trips, 1);
  expectedSolverCalls = after.solver;
  expectedWorkCounters = workCounters(after);
  await writeFile(
    join(output, "candidate-cache-result.json"),
    JSON.stringify(
      {
        passed: true,
        primaryAssessmentUnsaved: true,
        primaryOneDayElapsed: assessment.candidate.one_day.elapsed_seconds,
        cachedConfirmationStatus: duplicate.status,
        cancelledConfirmationStatus: cancelledConfirm.status,
        flexibleMissingOccupancyStatus: missingOccupancy.status,
        flexibleMode: confirmed.data.trip_mode,
        flexibleHotelStops: confirmed.data.stops.filter(
          (stop) => stop.type === "hotel",
        ).length,
        modelCountersBeforeFlexibleConfirm: workCounters(afterAssessment),
        modelCountersAfter: workCounters(after),
      },
      null,
      2,
    ) + "\n",
  );
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
  const assessment = await enterTrip(page, future);
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
  await candidateCacheAndFlexibleChecks(page, assessment);
  await page.getByRole("link", { name: "Open trip", exact: true }).click();
  await page
    .getByRole("heading", { name: "Trip details", exact: true })
    .waitFor();
  await page
    .getByRole("region", { name: "Meal breaks", exact: true })
    .waitFor();
  const created = await fixtureReport();
  assertReservedMeals(created.trips[0].data);
  assertOneDay(created.trips[0].data.route);
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
  await page
    .getByRole("button", { name: "Correct an arrival", exact: true })
    .click();
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
    .getByRole("button", { name: "Correct an arrival", exact: true })
    .click();
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
  assertOneDay(edited.trips[0].data.route);
  assert.equal(
    Object.hasOwn(edited.trips[0].data.presentation, "arrivals"),
    false,
    "Route edits must clear obsolete arrival events",
  );
  assert.equal(
    Object.hasOwn(
      edited.trips[0].data.presentation,
      "automaticArrivalExcludedStopIds",
    ),
    false,
    "Route edits must clear old automatic-arrival undo exclusions",
  );
  assert.deepEqual(edited.trips[0].data.presentation.visitedStopIds, []);
  await page.getByRole("link", { name: "Back to trip", exact: true }).click();
  await page.reload();
  await page
    .getByRole("button", { name: "Correct an arrival", exact: true })
    .click();
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
  await page
    .getByRole("button", { name: "Correct an arrival", exact: true })
    .click();
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
    .getByRole("slider", { name: "Start driving", exact: true })
    .press("ArrowLeft");
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
      .getByRole("slider", { name: "Start driving", exact: true })
      .inputValue(),
    "8",
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
  assert.equal(
    profile.choices.scheduling_policy.daily_schedule.slots.length,
    24,
  );
  assert.equal(
    profile.choices.scheduling_policy.daily_schedule.slots[8],
    "drive",
  );
  assert.equal(
    profile.choices.scheduling_policy.daily_schedule.slots[7],
    "rest",
  );
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
  const tripFields = [
    "Starting city or address",
    "Destination",
    "Departure date",
    "Departure time",
  ];
  const beforePreferences = await Promise.all(
    tripFields.map((label) =>
      page.getByLabel(label, { exact: true }).inputValue(),
    ),
  );
  await page.getByText("Use saved preferences", { exact: true }).click();
  await page
    .getByLabel("Saved preferences", { exact: true })
    .selectOption(profile.id);
  await page
    .getByRole("button", { name: "Load preferences", exact: true })
    .click();
  await page.getByText("Preferences loaded.", { exact: true }).waitFor();
  assert.deepEqual(
    await Promise.all(
      tripFields.map((label) =>
        page.getByLabel(label, { exact: true }).inputValue(),
      ),
    ),
    beforePreferences,
    "Loading preferences must preserve this trip's locations and departure",
  );
  for (let step = 0; step < 3; step++) {
    await page.getByRole("button", { name: "Next", exact: true }).click();
    if (step === 0)
      assert.equal(
        await page
          .getByLabel("How many attractions would you like?", { exact: true })
          .inputValue(),
        "3",
        "Loading preferences must preserve this trip's stop count",
      );
  }
  assert.equal(
    await page
      .getByRole("slider", { name: "Start driving", exact: true })
      .inputValue(),
    "8",
  );
  await page.goto(frontend + "/trip");
  await page.reload();
  await page
    .getByRole("button", { name: "Correct an arrival", exact: true })
    .click();
  await page
    .getByRole("button", {
      name: "Mark visited: Synthetic edit stop",
      exact: true,
    })
    .waitFor();
  const happyReport = await (await fetch(backend + "/fixture/report")).json();
  assert.equal(happyReport.stored_trips, 1);
  assert.equal(happyReport.solver, expectedSolverCalls);
  assert.deepEqual(
    workCounters(happyReport),
    expectedWorkCounters,
    "Edits, Settings and preference reuse must not start another model-backed assessment",
  );
  assert.equal(happyReport.hotel_requests, 0);
  assert.ok(happyReport.browse > 0 && happyReport.current_facts > 0);
  assertReservedMeals(happyReport.trips[0].data);
  await writeFile(
    join(output, "happy-result.json"),
    JSON.stringify({ passed: true, report: happyReport }, null, 2) + "\n",
  );
  console.log(
    "PASS: actual trip creation, reserved meals, sequential visit revisions, stale rejection, edit preview/save/reload and Settings profile/car persistence in disposable PostgreSQL.",
  );
  await sharedOnlyHomeChecks(page);
  await context.close();

  const failed = await session({ homePath: "/trips" });
  await enterTrip(failed.page, "2000-01-01", { expectFailure: true });
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
  assert.equal(report.login, 3);
  assert.ok(
    report.catalog > 0 &&
      report.ratings > 0 &&
      report.durations > 0 &&
      report.gateway_auth > 0,
  );
  assert.equal(
    report.solver,
    expectedSolverCalls,
    "The rejected expired trip must not execute another solve",
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
    report.requests.filter(
      (r) => r.method === "POST" && r.path === "/planning-candidates/stream",
    ).length,
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
  assert.equal(report.hotel_requests, 0);
  assert.deepEqual(
    workCounters(report),
    expectedWorkCounters,
    "The expired attempt must fail before AI work or another solve",
  );
  assert.equal(
    report.requests.filter(
      (request) => request.path === "/generate-final-route/stream",
    ).length,
    0,
    "Current UI must use the actual registered candidate flow",
  );
  assert.deepEqual(blocked, []);
  assert.deepEqual(errors, []);
  for (const phase of ["considering", "selected", "checking"])
    assert.ok(
      report.preview_events.some(
        (event) =>
          event.phase === phase &&
          event.preview_only === true &&
          event.geometry.coordinates.length >= 2,
      ),
      `The primary actual planner stream must emit its ${phase} map preview`,
    );
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
  await runOvernightJourney({
    session,
    api,
    fixtureReport,
    assertWidths,
    assertOrdinarySetupFit,
    frontend,
    output,
  });
  await writeFile(
    join(output, "ordinary-phone-setup-fit.json"),
    JSON.stringify(ordinarySetupFits, null, 2) + "\n",
  );
  assert.deepEqual(blocked, []);
  assert.deepEqual(errors, []);
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
