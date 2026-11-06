// Dedicated, intercepted local fixtures. Never connect this check to a live provider.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
const toolsDir =
  process.env.UI_BROWSER_TOOLS_DIR || "/tmp/roadtrips-ui-browser";
const { chromium } = await import(
  pathToFileURL(join(toolsDir, "node_modules/playwright-core/index.mjs"))
);
const { default: AxeBuilder } = await import(
  pathToFileURL(
    join(toolsDir, "node_modules/@axe-core/playwright/dist/index.mjs"),
  )
);
const out =
  process.env.ROADTRIPS_UI_EVIDENCE_DIR ||
  "/tmp/roadtrips-ui-integration-evidence";
await fs.mkdir(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  headless: true,
  args: ["--no-sandbox"],
});
const context = await browser.newContext({
  viewport: { width: 1365, height: 900 },
  reducedMotion: "reduce",
});
const page = await context.newPage(),
  errors = [],
  requests = [],
  violations = [],
  blocked = [];
page.on("pageerror", (error) => errors.push(error.message));
await context.addInitScript(() => {
  if (sessionStorage.getItem("fixture-started")) return;
  sessionStorage.setItem("fixture-started", "true");
  for (const use of ["access", "id"]) {
    const token =
      "header." +
      btoa(
        JSON.stringify({
          iss: "fixture",
          sub: "ui-integration",
          token_use: use,
          exp: Date.now() / 1000 + 3600,
        }),
      ) +
      ".fixture";
    sessionStorage.setItem(use + "Token", token);
  }
});
const origin = {
  address: "Boulder, Colorado",
  latitude: 40.01,
  longitude: -105.27,
};
const destination = {
  address: "Denver, Colorado",
  latitude: 39.74,
  longitude: -104.99,
};
const route = {
  coordinates: [
    [40.01, -105.27],
    [39.74, -104.99],
  ],
  geometry: {
    type: "LineString",
    coordinates: [
      [-105.27, 40.01],
      [-104.99, 39.74],
    ],
  },
  distance: 160000,
  duration: 7200,
  steps: [],
  cost: 0,
  start_timezone: "America/Denver",
  departure_time: "2027-06-01T09:00:00-06:00",
  stops: [
    {
      name: "Fixture destination",
      coordinates: [39.74, -104.99],
      type: "end",
      duration: 7200,
      visit_duration_seconds: 2700,
      leaving_time: "2027-06-01T11:45:00-06:00",
    },
  ],
};
const itinerary = [
  {
    date: "Fixture day",
    stops: [
      {
        name: "Fixture destination",
        time: "11:00 AM",
        address: destination.address,
      },
    ],
  },
];
const old = [
  {
    chatId: 7,
    startConfirmed: origin,
    endConfirmed: destination,
    route,
    itinerary,
    tripProfile: {},
  },
  {
    id: 7,
    title: "Existing saved trip",
    messages: [{ text: "Historical text must stay stored", sender: "bot" }],
  },
];
const baseline = JSON.stringify(old),
  rows = [old];
let finalPayload,
  itineraryCalls = 0;
await page.route("**/*", async (intercepted) => {
  const request = intercepted.request(),
    url = new URL(request.url());
  if (url.origin === "http://127.0.0.1:5187") return intercepted.continue();
  if (url.origin !== "http://127.0.0.1:18987") {
    blocked.push(url.origin);
    return intercepted.abort();
  }
  const path = url.pathname,
    method = request.method();
  requests.push({ path, method });
  const json = (data, status = 200) =>
    intercepted.fulfill({
      status,
      contentType: "application/json",
      headers: {
        "access-control-allow-origin": "*",
        "access-control-allow-headers": "*",
        "access-control-allow-methods": "*",
      },
      body: JSON.stringify(data),
    });
  if (method === "OPTIONS") return json({});
  if (path.startsWith("/agent/")) throw new Error("Retired endpoint requested");
  if (path === "/chats" && method === "GET") return json(rows);
  if (path === "/routing-settings")
    return json({
      can_select_algorithm: false,
      expires_at: Date.now() / 1000 + 3600,
    });
  if (path === "/validate-location") {
    const address = request.postDataJSON().location.address;
    if (address === "Boulder")
      return json(
        {
          detail: {
            candidates: [
              { address: "Boulder, Utah", latitude: 37.9, longitude: -111.4 },
              origin,
            ],
          },
        },
        409,
      );
    return json(destination);
  }
  if (path === "/get-initial-route") {
    assert.equal(url.searchParams.get("start_lat"), String(origin.latitude));
    return json({
      geometry: route.geometry,
      distance: 160000,
      duration: 7200,
      weight: 7200,
      weight_name: "duration",
      legs: [
        {
          admins: [],
          weight: 7200,
          duration: 7200,
          steps: [],
          distance: 160000,
          summary: "fixture",
        },
      ],
    });
  }
  if (path === "/generate-final-route") {
    finalPayload = request.postDataJSON();
    assert.equal(Object.keys(finalPayload.persona_weights).length, 14);
    assert.equal(
      finalPayload.persona_weights.food > finalPayload.persona_weights.history,
      true,
    );
    assert.equal(finalPayload.start, "2027-06-01T09:00:00");
    assert.equal("message" in finalPayload, false);
    return json(route);
  }
  if (path === "/generate-itinerary") {
    itineraryCalls++;
    assert.equal(
      request.postDataJSON().route.stops[0].visit_duration_seconds,
      2700,
    );
    return itineraryCalls === 1
      ? json({ detail: "Local fixture temporary itinerary failure" }, 503)
      : json(itinerary);
  }
  if (path.startsWith("/chats/create/")) {
    const data = request.postDataJSON();
    assert.notEqual(data.ChatData.chatId, 7);
    assert.deepEqual(data.ChatLog.messages, []);
    assert.equal(data.ChatData.hotelBudget, null);
    assert.equal(data.ChatData.tripProfile.budget, 150.25);
    assert.equal(
      rows.some(([record]) => record.chatId === data.ChatData.chatId),
      false,
    );
    rows.push([data.ChatData, data.ChatLog]);
    return json({});
  }
  if (path.startsWith("/chats/update/")) {
    const data = request.postDataJSON(),
      index = rows.findIndex(
        ([record]) => record.chatId === data.ChatData.chatId,
      );
    assert.ok(
      index > 0,
      "Create must precede update; existing trip must not be rewritten",
    );
    rows[index] = [data.ChatData, data.ChatLog];
    return json({});
  }
  return json({ detail: "No live services in this fixture" }, 503);
});
async function audit(name) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  violations.push({
    name,
    violations: result.violations.map(({ id, impact, nodes }) => ({
      id,
      impact,
      targets: nodes.map((node) => node.target),
    })),
  });
}
async function capture(name) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    document.getElementById("fixture-caption")?.remove();
    const label = document.createElement("aside");
    label.id = "fixture-caption";
    label.textContent =
      "LOCAL STRUCTURED-API FIXTURE — no live AI, provider or database results";
    label.style =
      "font:12px/1.5 system-ui;background:#1d2430;color:white;padding:8px;margin-top:24px";
    document.querySelector("main").append(label);
  });
  await page.screenshot({ path: join(out, name + ".png"), fullPage: true });
}
try {
  await page.goto("http://127.0.0.1:5187/");
  await page.getByRole("link", { name: /Plan a trip A few/ }).click();
  await page
    .getByLabel("Starting city or address", { exact: true })
    .fill("Boulder");
  await page.getByLabel("Destination", { exact: true }).fill("Denver");
  await page.getByLabel("Departure date", { exact: true }).fill("2027-06-01");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page
    .getByLabel("Hotel target per room, per night (USD)", { exact: true })
    .fill("150.25");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page.getByRole("checkbox", { name: "Food", exact: true }).check();
  await page.reload();
  assert.equal(
    await page.getByRole("checkbox", { name: "Food", exact: true }).isChecked(),
    true,
  );
  await page.setViewportSize({ width: 320, height: 800 });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
  await audit("interests-320");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page
    .getByLabel("Would you like to add your car?")
    .selectOption("skipped");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await page
    .getByRole("button", { name: "Check locations", exact: true })
    .click();
  await page.getByRole("heading", { name: "Confirm your locations" }).waitFor();
  assert.equal(
    requests.some(({ path }) => path === "/generate-final-route"),
    false,
  );
  await page.getByLabel("Boulder, Colorado", { exact: true }).check();
  await page.setViewportSize({ width: 390, height: 844 });
  await audit("address-confirmation-mobile");
  await capture("structured-confirmation-mobile");
  await page
    .getByRole("button", { name: "Confirm locations and plan route" })
    .click();
  await page.getByText("Trip saved.", { exact: true }).waitFor();
  assert.equal(
    await page
      .getByRole("link", { name: "View itinerary", exact: true })
      .count(),
    0,
  );
  await page.getByRole("button", { name: "Retry itinerary" }).click();
  await page
    .getByRole("link", { name: "View itinerary", exact: true })
    .waitFor();
  assert.equal(
    requests.filter(({ path }) => path === "/generate-final-route").length,
    1,
  );
  await audit("structured-results-mobile");
  await capture("structured-result-mobile");
  await page.getByRole("link", { name: "View itinerary", exact: true }).click();
  await page.getByText("Fixture destination", { exact: true }).waitFor();
  await page.reload();
  await page.getByText("Fixture destination", { exact: true }).waitFor();
  await page
    .getByRole("link", { name: "Saved trips", exact: true })
    .first()
    .click();
  await page.getByRole("heading", { name: "Existing saved trip" }).waitFor();
  assert.equal(
    await page.getByText("Historical text must stay stored").count(),
    0,
  );
  await page
    .getByRole("link", { name: "View map", exact: true })
    .last()
    .click();
  await page
    .getByRole("group", {
      name: "Local route map from Boulder, Colorado to Denver, Colorado",
    })
    .waitFor();
  await page.reload();
  await page
    .getByRole("group", {
      name: "Local route map from Boulder, Colorado to Denver, Colorado",
    })
    .waitFor();
  await page.goto("http://127.0.0.1:5187/chat");
  await page
    .getByRole("heading", { name: "Saved trips", exact: true })
    .waitFor();
  assert.equal(new URL(page.url()).pathname, "/trips");
  await page.getByRole("link", { name: "AI Studio", exact: true }).click();
  await page.getByLabel("Password", { exact: true }).waitFor();
  assert.equal(JSON.stringify(old), baseline);
  assert.ok(!requests.some(({ path }) => path.startsWith("/agent/")));
  assert.deepEqual(errors, []);
  assert.ok(
    blocked.every(
      (origin) =>
        origin === "https://fonts.googleapis.com" ||
        origin === "https://fonts.gstatic.com",
    ),
    "Unexpected external service was requested; every external request is blocked",
  );
  await fs.writeFile(
    join(out, "contract-fixture.json"),
    JSON.stringify({ trip: rows.at(-1), route_payload: finalPayload }),
  );
  await fs.writeFile(
    join(out, "browser-results.json"),
    JSON.stringify(
      {
        scope: "Structured local API fixtures only; no live Mentro calls",
        requests,
        violations,
        errors,
        blocked,
        originalSavedRowUnchanged: JSON.stringify(old) === baseline,
      },
      null,
      2,
    ),
  );
  assert.ok(violations.every((item) => !item.violations.length));
  console.log(JSON.stringify({ passed: true, requests, violations }, null, 2));
} finally {
  await browser.close();
}
