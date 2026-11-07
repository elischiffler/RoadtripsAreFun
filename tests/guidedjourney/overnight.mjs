import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";

const slotsFor = (sleepStart, sleepEnd) =>
  Array.from({ length: 24 }, (_, hour) =>
    hour >= 20 || hour < 6
      ? "drive"
      : hour >= sleepStart && hour < sleepEnd
        ? "sleep"
        : "rest",
  );
const schedule = { slots: slotsFor(8, 16), timezone: "route_local" };
const occupants = [{ adults: 2, child_ages: [7] }];
const time = (value) => {
  const result = Date.parse(value);
  assert.ok(Number.isFinite(result), `Expected a complete timestamp: ${value}`);
  return result;
};
const day = (value, offset) =>
  new Date(time(value + "T00:00:00Z") + offset * 86400000)
    .toISOString()
    .slice(0, 10);

function assertOvernight(data, quotes) {
  const route = data.route;
  assert.equal(route.trip_mode, "overnight");
  assert.equal(route.reserve_meal_slots, true);
  assert.deepEqual(route.scheduling_policy.daily_schedule, schedule);
  assert.equal(route.traveler_count, 3);
  assert.deepEqual(route.hotel_rooms, occupants);
  assert.equal(route.departure_time.slice(11, 16), "20:00");
  const hotels = route.stops.filter((stop) => stop.type === "hotel");
  assert.ok(hotels.length > 0, "The long route must actually include lodging");
  const sleep = hotels.flatMap((hotel) =>
    hotel.daily_rhythm_blocks.filter((block) => block.kind === "sleep"),
  );
  assert.ok(sleep.length > 0, "Physical hotel rest must include daytime sleep");
  for (const block of sleep) {
    assert.equal(block.arrival_time.slice(11, 16), "08:00");
    assert.equal(block.departure_time.slice(11, 16), "16:00");
    assert.equal(
      time(block.departure_time) - time(block.arrival_time),
      8 * 3600000,
    );
  }
  assert.ok(
    route.stops.at(-1).arrival_time.slice(0, 10) >
      route.departure_time.slice(0, 10),
    "The actual route must roll over its departure date",
  );
  assert.ok(
    time(route.stops.at(-1).arrival_time) - time(route.departure_time) >
      86400000,
    "The verified route must span more than a full elapsed day",
  );
  assert.ok(
    Math.abs(
      route.duration -
        route.stops.reduce((sum, stop) => sum + stop.duration, 0),
    ) < 1,
    "The route must retain the actual returned road-leg durations",
  );
  let previous = route.departure_time;
  let crossedMidnight = false;
  for (const stop of route.stops) {
    const roadArrival = stop.road_arrival_time || stop.arrival_time;
    assert.ok(time(roadArrival) - time(previous) + 1 >= stop.duration * 1000);
    crossedMidnight ||=
      previous.slice(0, 10) < roadArrival.slice(0, 10) && stop.duration > 0;
    previous = stop.departure_time;
  }
  assert.ok(crossedMidnight, "An actual road leg must cross midnight");
  const meals = route.stops.flatMap((stop) => stop.meal_breaks || []);
  assert.ok(meals.some((meal) => meal.meal_type === "breakfast"));
  assert.ok(meals.some((meal) => meal.meal_type === "lunch"));
  assert.ok(meals.some((meal) => meal.meal_type === "dinner"));
  for (const meal of meals) {
    const start = time(meal.arrival_time);
    const end = time(meal.departure_time);
    assert.ok(time(meal.window_start) <= start && end <= time(meal.window_end));
    assert.deepEqual(
      [meal.window_start.slice(11, 16), meal.window_end.slice(11, 16)],
      {
        breakfast: ["16:00", "18:00"],
        lunch: ["21:00", "23:00"],
        dinner: ["03:00", "05:00"],
      }[meal.meal_type],
      "Explicit daytime sleep shifts windows by wake time without shortening meals",
    );
    if (meal.meal_type === "dinner")
      assert.equal(
        meal.id,
        `meal:${day(meal.window_start.slice(0, 10), -1)}:dinner`,
      );
    assert.equal(
      (end - start) / 1000,
      { breakfast: 1800, lunch: 2700, dinner: 3600 }[meal.meal_type],
    );
    for (const block of sleep)
      assert.ok(
        end <= time(block.arrival_time) || start >= time(block.departure_time),
        "A reserved meal must not overlap daytime sleep",
      );
    for (const stop of route.stops.filter((item) => item.type === "stop"))
      assert.ok(
        end <= time(stop.arrival_time) || start >= time(stop.departure_time),
        "A reserved meal must not overlap an attraction visit",
      );
  }
  for (const hotel of hotels) {
    assert.deepEqual(hotel.hotel_rooms, occupants);
    assert.equal(hotel.traveler_count, 3);
    assert.ok(time(hotel.departure_time) > time(hotel.arrival_time));
    assert.equal(hotel.departure_time.slice(11, 16), "20:00");
    assert.equal(hotel.check_in_date, day(hotel.arrival_time.slice(0, 10), -1));
    assert.equal(
      hotel.check_out_date,
      day(hotel.departure_time.slice(0, 10), 1),
    );
    assert.equal(hotel.lodging.check_in_date, hotel.check_in_date);
    assert.equal(hotel.lodging.check_out_date, hotel.check_out_date);
    assert.equal(hotel.lodging.nights, 2);
    assert.equal(hotel.lodging.access_status, "confirmation_required");
    assert.equal(time(hotel.lodging.planned_arrival), time(hotel.arrival_time));
    assert.equal(
      time(hotel.lodging.planned_departure),
      time(hotel.departure_time),
    );
    assert.match(hotel.lodging.notice, /confirm/i);
    assert.deepEqual(
      hotel.daily_rhythm_blocks.map((block) => block.kind),
      ["rest", "sleep", "rest"],
    );
    assert.equal(
      hotel.daily_rhythm_blocks.reduce(
        (sum, block) => sum + block.duration_seconds,
        0,
      ),
      (time(hotel.departure_time) - time(hotel.arrival_time)) / 1000,
    );
    const matching = quotes.filter(
      (quote) =>
        quote.provider_id === hotel.provider_id &&
        quote.check_in_date === hotel.check_in_date,
    );
    assert.ok(
      matching.length > 0,
      "Hotel dates must match an actual provider request",
    );
    assert.deepEqual(matching[0].room, occupants[0]);
    assert.equal(matching[0].check_out_date, hotel.check_out_date);
    assert.equal(matching[0].price, 250);
    assert.equal(hotel.price, matching[0].price);
    assert.equal(hotel.price_scope, "one_room_stay_including_taxes_fees");
    assert.deepEqual(hotel.room_offers[0].room, occupants[0]);
    assert.equal(hotel.room_offers[0].check_in_date, hotel.check_in_date);
    assert.equal(hotel.room_offers[0].check_out_date, hotel.check_out_date);
    assert.equal(hotel.room_offers[0].price, 250);
  }
  assert.equal(
    route.cost,
    hotels.reduce((sum, hotel) => sum + hotel.price, 0),
  );
  assert.ok(
    data.itinerary
      .flatMap((entry) => entry.stops)
      .some(
        (stop) =>
          stop.lodging?.nights === 2 &&
          stop.lodging.access_status === "confirmation_required",
      ),
  );
}

export async function runOvernightJourney({
  session,
  api,
  fixtureReport,
  assertWidths,
  output,
}) {
  const baseline = await fixtureReport();
  const { context, page } = await session({ email: "overnight@example.test" });
  try {
    const date = new Date(Date.now() + 8 * 86400000).toISOString().slice(0, 10);
    await page
      .getByLabel("Starting city or address", { exact: true })
      .fill("Boulder");
    await page
      .getByLabel("Destination", { exact: true })
      .fill("Synthetic overnight destination");
    await page.getByLabel("Departure date", { exact: true }).fill(date);
    await page.getByLabel("Departure time", { exact: true }).fill("20:00");
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page
      .getByLabel("Total people, including you", { exact: true })
      .fill("3");
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByRole("button", { name: "Next", exact: true }).click();
    for (const [name, value] of [
      ["Start driving", 20],
      ["Stop driving", 6],
      ["Start sleep", 8],
      ["Wake up", 16],
    ]) {
      const slider = page.getByRole("slider", { name, exact: true });
      await slider.focus();
      await slider.press("Home");
      for (let step = 0; step < value; step++) await slider.press("ArrowRight");
      assert.equal(await slider.inputValue(), String(value));
    }
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page
      .getByRole("button", { name: /^Tentative stay search area:/ })
      .first()
      .waitFor();
    const lastSequence = baseline.preparation_records.at(-1)?.sequence || 0;
    const deadline = Date.now() + 30000;
    let receipt;
    while (Date.now() < deadline) {
      receipt = (await fixtureReport()).preparation_records.find(
        (record) =>
          record.sequence > lastSequence &&
          record.request.departure_clock === "20:00" &&
          record.request.daily_schedule?.timezone === schedule.timezone &&
          JSON.stringify(record.request.daily_schedule?.slots) ===
            JSON.stringify(schedule.slots) &&
          record.events.at(-1)?.type === "result",
      );
      if (receipt) break;
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    assert.ok(receipt, "No complete preparation receipt for the final rhythm");
    assert.equal(receipt.status, 200);
    assert.equal(receipt.truncated, false);
    assert.equal(receipt.invalid_event, undefined);
    const preparationEvents = receipt.events;
    // Server receipt is not browser proof. Areas must render, loading must end,
    // and the actual map must switch to its ready geometry without fallback.
    await page
      .getByRole("img", { name: "Draft route geometry", exact: true })
      .waitFor();
    await page
      .getByText(/^Preparing catalog ideas ·/)
      .waitFor({ state: "detached" });
    assert.equal(
      await page
        .getByText(
          "Some catalog ideas could not be checked. You can continue planning.",
          { exact: true },
        )
        .count(),
      0,
    );
    const earlyAreas = preparationEvents.find(
      (event) => event.stage === "preparation.areas",
    );
    assert.equal(earlyAreas.preview_only, true);
    assert.equal(earlyAreas.phase, "preparing");
    assert.ok(earlyAreas.geometry.coordinates.length >= 2);
    assert.ok(earlyAreas.possible_overnight_areas.length > 0);
    for (const area of earlyAreas.possible_overnight_areas) {
      assert.equal(area.tentative, true);
      assert.equal(area.hotel_quotes_checked, false);
      assert.equal(area.availability_checked, false);
      assert.equal(area.clock_basis, "departure_wall_clock_estimate");
    }
    assert.deepEqual(
      preparationEvents
        .filter((event) => event.stage === "preparation.catalog")
        .map((event) => event.sections_checked),
      [1, 2, 3, 4, 5, 6],
    );
    assert.equal(preparationEvents.at(-1).type, "result");
    const prepared = await fixtureReport();
    assert.equal(prepared.gateway_requests, baseline.gateway_requests);
    assert.deepEqual(prepared.overnight_trips, []);
    await page
      .getByRole("button", { name: "Check trip options", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Allow hotel stays", exact: true })
      .waitFor({ timeout: 60000 });
    const checked = await fixtureReport();
    assert.deepEqual(checked.overnight_trips, []);
    assert.equal(checked.hotel_requests, baseline.hotel_requests);
    assert.ok(
      await page
        .getByRole("progressbar", {
          name: "Trip planning milestones",
          exact: true,
        })
        .evaluate((node) => node.max === 100 && node.value < 100),
    );
    await page
      .getByRole("button", { name: "Allow hotel stays", exact: true })
      .click();
    await page.getByLabel("Adults in room 1", { exact: true }).fill("2");
    await page.getByLabel("Child ages in room 1", { exact: true }).fill("7");
    await page
      .getByLabel("Hotel target per room / night", { exact: true })
      .fill("150");
    await page
      .getByRole("button", { name: "Plan with stays allowed", exact: true })
      .click();
    await Promise.race([
      page
        .getByText("Trip saved.", { exact: true })
        .waitFor({ timeout: 60000 }),
      page
        .getByRole("alert")
        .waitFor({ timeout: 60000 })
        .then(async () => {
          throw Error(
            "Actual overnight planning failed: " +
              (await page.getByRole("alert").innerText()),
          );
        }),
    ]);
    const created = await fixtureReport();
    assert.equal(created.overnight_trips.length, 1);
    assert.ok(created.hotel_requests > baseline.hotel_requests);
    assertOvernight(created.overnight_trips[0], created.hotel_quotes);
    await page.getByRole("link", { name: "Open trip", exact: true }).click();
    await page.reload();
    await page
      .getByRole("heading", { name: "Trip details", exact: true })
      .waitFor();
    const hotelNotice = created.overnight_trips[0].route.stops.find(
      (stop) => stop.type === "hotel",
    ).lodging.notice;
    await page
      .getByRole("region", { name: "Hotel quote dates", exact: true })
      .first()
      .getByText(hotelNotice, { exact: true })
      .waitFor();
    await assertWidths(page);
    const stored = await api(page, "/chats");
    assert.equal(stored.status, 200);
    const reloaded = stored.data[0][0];
    assertOvernight(reloaded, created.hotel_quotes);

    // A short awake cycle cannot fit every full shifted meal. Exercise the
    // actual itinerary/timing guard; never remove a meal or put it in sleep.
    const conflicting = structuredClone(reloaded.route);
    conflicting.scheduling_policy = {
      daily_schedule: { slots: slotsFor(6, 20), timezone: "route_local" },
    };
    const collision = await api(page, "/generate-itinerary", {
      method: "POST",
      body: { route: conflicting, include_meal_slots: true },
    });
    assert.equal(collision.status, 422);
    assert.equal(typeof collision.data.detail, "string");
    assert.match(collision.data.detail, /meal/i);
    assert.deepEqual(
      (await fixtureReport()).overnight_trips,
      created.overnight_trips,
    );

    await page
      .getByRole("navigation", { name: "Trip views" })
      .getByRole("link", { name: "Edit itinerary", exact: true })
      .click();
    await page
      .getByRole("heading", { name: "Edit itinerary", exact: true })
      .waitFor();
    await page
      .getByRole("button", { name: "Find places", exact: true })
      .click();
    await page
      .getByRole("button", {
        name: "Choose Synthetic overnight edit stop",
        exact: true,
      })
      .click();
    await page
      .getByRole("combobox", { name: /^Action/ })
      .selectOption("replace");
    const target = reloaded.route.stops
      .map((stop, index) => ({ stop, index }))
      .filter(({ stop }) => stop.type === "stop")
      .sort(
        (a, b) =>
          Math.abs(a.stop.coordinates[0] - 45) -
          Math.abs(b.stop.coordinates[0] - 45),
      )[0];
    assert.ok(target);
    await page
      .getByRole("combobox", { name: /^Replace/ })
      .selectOption(String(target.index));
    await page
      .getByRole("button", { name: "Recalculate trip", exact: true })
      .click();
    await page
      .getByRole("heading", { name: "Review changes", exact: true })
      .waitFor({ timeout: 30000 });
    assert.deepEqual(
      (await fixtureReport()).overnight_trips,
      created.overnight_trips,
    );
    await page
      .getByRole("button", { name: "Save changes", exact: true })
      .click();
    await page.getByText("Trip changes saved.", { exact: true }).waitFor();
    await page.getByRole("link", { name: "Back to trip", exact: true }).click();
    await page.reload();
    await page
      .getByRole("heading", { name: "Trip details", exact: true })
      .waitFor();
    const edited = await api(page, "/chats");
    assert.equal(edited.status, 200);
    assertOvernight(edited.data[0][0], created.hotel_quotes);
    assert.ok(
      edited.data[0][0].route.stops.some(
        (stop) => stop.provider_id === "overture:guided-overnight-edit",
      ),
    );
    await page.screenshot({
      path: join(output, "overnight-reloaded.png"),
      fullPage: true,
    });
    const final = await fixtureReport();
    assert.deepEqual(final.trips, baseline.trips);
    assert.deepEqual(final.blocked_network, []);
    const ownPreviews = final.preview_events.slice(
      baseline.preview_events.length,
    );
    for (const phase of ["considering", "selected"]) {
      assert.ok(
        ownPreviews.some(
          (event) =>
            event.phase === phase &&
            event.preview_only === true &&
            event.geometry.coordinates.length >= 2,
        ),
        `Actual planner must emit its ${phase} map preview`,
      );
    }
    await writeFile(
      join(output, "overnight-result.json"),
      JSON.stringify(
        {
          passed: true,
          scope:
            "Actual browser/API/solver/timing/dated-hotel validation/room intersection/CRUD/disposable PostgreSQL; synthetic remote provider records and gateway replies, no real availability claim.",
          mealCollisionStatus: collision.status,
          preparationSections: 6,
          ownCandidatePreviewPhases: [
            ...new Set(ownPreviews.map((event) => event.phase)),
          ],
          tentativeAreas: earlyAreas.possible_overnight_areas,
          hotelRequests: final.hotel_requests - baseline.hotel_requests,
          hotelQuotes: final.hotel_quotes,
          route: edited.data[0][0].route,
        },
        null,
        2,
      ) + "\n",
    );
    console.log(
      "PASS: actual overnight lodging, cross-midnight driving, daytime sleep, meal conflict, save/reload and rhythm-preserving edit.",
    );
  } catch (error) {
    await page
      .screenshot({
        path: join(output, "overnight-failure.png"),
        fullPage: true,
        timeout: 5000,
      })
      .catch(() => {});
    await writeFile(
      join(output, "overnight-failure.json"),
      JSON.stringify(
        {
          passed: false,
          error: error.message,
          report: await fixtureReport(),
        },
        null,
        2,
      ) + "\n",
    );
    throw error;
  } finally {
    await context.close();
  }
}
