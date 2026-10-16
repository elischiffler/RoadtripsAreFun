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
import fs from "node:fs/promises";
import assert from "node:assert/strict";
const out =
  process.env.ROADTRIPS_UI_EVIDENCE_DIR || "/tmp/roadtrips-ui-evidence";
await fs.mkdir(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  headless: true,
  args: ["--no-sandbox"],
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1050 },
  reducedMotion: "reduce",
});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const reports = [],
  requests = [],
  updates = [];
const token = (kind) =>
  "header." +
  Buffer.from(
    JSON.stringify({
      iss: "fixture",
      sub: "ui-review",
      exp: Date.now() / 1000 + 3600,
      token_use: kind,
    }),
  ).toString("base64") +
  ".signature";
await context.addInitScript(
  ({ access, id }) => {
    if (sessionStorage.getItem("fixture-auth-installed")) return;
    sessionStorage.setItem("fixture-auth-installed", "1");
    sessionStorage.setItem("accessToken", access);
    sessionStorage.setItem("idToken", id);
    sessionStorage.setItem("sessionOwner", "fixture:ui-review");
    sessionStorage.setItem("selectedChatId", "7");
  },
  { access: token("access"), id: token("id") },
);
let profile = {},
  mismatch = false;
await page.route("http://127.0.0.1:18084/**", async (route) => {
  const request = route.request(),
    url = new URL(request.url()),
    path = url.pathname;
  const headers = {
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "*",
    "access-control-allow-methods": "*",
  };
  const json = (data, status = 200) =>
    route.fulfill({
      status,
      headers,
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  if (request.method() === "OPTIONS") return json({});
  if (path === "/chats" && request.method() === "GET")
    return json([
      [
        { chatId: 7, agentChatId: "saved-fixture-trip", tripProfile: {} },
        {
          id: 7,
          title: "Example saved trip",
          messages: [
            { sender: "bot", text: "A saved example, unchanged by setup." },
          ],
        },
      ],
    ]);
  if (path === "/routing-settings")
    return json({
      can_select_algorithm: false,
      expires_at: Date.now() / 1000 + 3600,
      algorithms: ["cp_sat"],
      default: "cp_sat",
    });
  if (path.startsWith("/chats/create/")) {
    requests.push({ path, body: request.postDataJSON() });
    return json({});
  }
  if (path.startsWith("/chats/update/")) {
    updates.push(request.postDataJSON());
    return json({});
  }
  if (path === "/agent/chat/stream") {
    const body = request.postDataJSON();
    requests.push({ path, body });
    if (body.message.includes("Trip-only persona_weights:")) {
      const [detailsText, weightsText] = body.message
        .split("Trip details: ")[1]
        .split("\nTrip-only persona_weights: ");
      const details = JSON.parse(detailsText),
        weights = JSON.parse(weightsText);
      profile = {
        ...details,
        persona_weights: mismatch
          ? Object.fromEntries(Object.keys(weights).map((k) => [k, 1 / 14]))
          : weights,
        pending_locations: {
          start_address: {
            query: details.start_address,
            candidates: [
              { id: "fixture-start", address: "Boulder, Colorado, USA" },
            ],
          },
          destination_address: {
            query: details.destination_address,
            candidates: [
              { id: "fixture-end", address: "Denver, Colorado, USA" },
            ],
          },
        },
      };
    }
    const response = {
      reply:
        "Local fixture receipt. No live route, price or provider data was produced.",
      tripProfile: profile,
      actions: [
        { type: "trip_profile_updated", payload: { trip_profile: profile } },
      ],
      validationIssues: {},
      toolsUsed: ["record_trip_details", "update_trip_profile"],
    };
    return route.fulfill({
      status: 200,
      headers,
      contentType: "application/x-ndjson",
      body: JSON.stringify({ type: "result", response }) + "\n",
    });
  }
  if (path === "/studio/access")
    return json({
      token: "local-studio-fixture",
      expires_at: Date.now() / 1000 + 3600,
    });
  if (path === "/studio/presets")
    return json({
      schema_version: 1,
      attributes: Object.keys(profile.persona_weights || {}),
      endpoints: [
        { id: "boulder", label: "Boulder, Colorado" },
        { id: "denver", label: "Denver, Colorado" },
      ],
      limits: {
        min_stops: 1,
        max_stops: 20,
        max_rooms: 8,
        max_guests_per_room: 8,
        max_child_age: 17,
      },
      presets: [
        {
          id: "local-example",
          label: "Local UI example",
          description: "UI fixture only",
          inputs: {
            start_id: "boulder",
            destination_id: "denver",
            departure_date: "2027-06-01",
            departure_time: "09:00",
            num_stops: 3,
            traveler_count: 1,
            hotel_rooms: [{ adults: 1, child_ages: [] }],
            budget: 150,
            car_status: "skipped",
            car: null,
            persona_weights: profile.persona_weights,
            scheduling_policy: {
              preferred_hotel_arrival: "18:00",
              latest_hotel_arrival: "20:00",
              latest_destination_arrival: "21:00",
              morning_restart: "09:00",
              late_driving: false,
              late_cutoff: "24:00",
            },
            evening_interests: [],
          },
        },
      ],
    });
  if (path === "/studio/runs") return json({ runs: [], groups: [] });
  return json(
    { detail: "No live calls are configured in this local fixture." },
    503,
  );
});
async function audit(name) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  reports.push({
    name,
    violations: result.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      description: v.description,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  });
}
async function capture(name) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.evaluate(() => {
    document.getElementById("fixture-label")?.remove();
    const e = document.createElement("aside");
    e.id = "fixture-label";
    e.textContent =
      "LOCAL UI FIXTURE · no live route, price or provider results";
    e.style =
      "display:block;margin-top:24px;border-radius:6px;background:#1d2430;color:white;font:12px/1.5 system-ui;padding:7px 12px;text-align:center";
    document.querySelector("main").append(e);
  });
  await page.screenshot({ path: out + "/" + name + ".png", fullPage: true });
}
await page.goto("http://127.0.0.1:5174/");
await page
  .getByRole("heading", { name: "The journey is part of the trip." })
  .waitFor();
await audit("home-desktop");
await capture("home-desktop");
await page.getByRole("link", { name: /Plan a trip A few/ }).click();
await page
  .getByRole("heading", { name: "Where and when", exact: true })
  .waitFor();
await page.keyboard.press("Tab");
assert.equal(
  await page
    .getByLabel("Starting city or address", { exact: true })
    .evaluate((e) => e === document.activeElement),
  true,
);
await page.getByRole("button", { name: "Next", exact: true }).click();
assert.equal(
  await page.getByRole("alert").evaluate((e) => e === document.activeElement),
  true,
);
await page
  .getByLabel("Starting city or address", { exact: true })
  .fill("Boulder");
await page.getByLabel("Destination", { exact: true }).fill("Denver");
await page.getByLabel("Departure date", { exact: true }).fill("2027-06-01");
await audit("setup-step-one");
await capture("setup-desktop");
await page.getByRole("button", { name: "Next", exact: true }).click();
await page.getByRole("button", { name: "Next", exact: true }).click();
await page.getByRole("checkbox", { name: "Food", exact: true }).check();
const place = page
  .getByRole("article")
  .filter({ has: page.getByRole("heading", { name: "Halfway House" }) });
await place.getByLabel("Very interested", { exact: true }).check();
await place.getByRole("checkbox", { name: "Nature", exact: true }).check();
await audit("setup-interests-desktop");
await capture("interests-desktop");
await page.reload();
await page
  .getByRole("heading", { name: "What you enjoy", exact: true })
  .waitFor();
assert.equal(
  await page.getByRole("checkbox", { name: "Food", exact: true }).isChecked(),
  true,
);
await page.setViewportSize({ width: 390, height: 844 });
await audit("setup-interests-mobile");
await capture("interests-mobile");
await page.setViewportSize({ width: 320, height: 800 });
assert.equal(
  await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth,
  ),
  true,
);
await audit("setup-interests-320");
await page.setViewportSize({ width: 390, height: 844 });
assert.equal(
  await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth,
  ),
  true,
);
assert.equal(
  await page
    .locator(".setup-section")
    .evaluate((e) => getComputedStyle(e).animationName),
  "none",
);
await page.getByRole("button", { name: "Next", exact: true }).click();
await page
  .getByLabel("Would you like to add your car?")
  .selectOption("skipped");
await page.getByRole("button", { name: "Next", exact: true }).click();
await audit("review-mobile");
await capture("review-mobile");
await page
  .getByRole("button", { name: "Send details for confirmation" })
  .click();
await page
  .getByRole("heading", { name: "Your interests are confirmed." })
  .waitFor();
const submission = requests.find((r) => r.path === "/agent/chat/stream");
assert.equal(submission.body.chatId === "saved-fixture-trip", false);
assert.equal(Object.keys(profile.persona_weights).length, 14);
assert.equal(
  profile.persona_weights.food > profile.persona_weights.history,
  true,
);
assert.equal(
  requests.some((r) => r.path === "/chats/create/7"),
  false,
);
await page.getByRole("button", { name: "Continue in chat" }).click();
await page.getByRole("button", { name: "Confirm both locations" }).waitFor();
assert.equal(new URL(page.url()).pathname, "/chat");
// Re-open an editable draft; a mismatching server profile must not claim confirmation.
await page.goto("http://127.0.0.1:5174/plan");
await page.getByRole("heading", { name: "Review", exact: true }).waitFor();
mismatch = true;
await page
  .getByRole("button", { name: "Send details for confirmation" })
  .click();
await page
  .getByRole("heading", { name: "Your interests aren’t confirmed yet." })
  .waitFor();
await capture("unconfirmed-mobile");
// Text zoom equivalent: double root font size, keep the viewport narrow.
await page.evaluate(() => (document.documentElement.style.fontSize = "200%"));
assert.equal(
  await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth,
  ),
  true,
);
await audit("review-mobile-200-percent-text");
await page.evaluate(() => (document.documentElement.style.fontSize = ""));
await page.goto("http://127.0.0.1:5174/studio");
await page.getByRole("heading", { name: "Enter Studio password" }).waitFor();
await page.getByLabel("Password", { exact: true }).fill("local-fixture-only");
await page.getByRole("button", { name: "Enter Studio", exact: true }).click();
await page.getByRole("button", { name: "Run live route" }).waitFor();
await page.getByRole("button", { name: "History", exact: true }).click();
await page.getByRole("table").waitFor();
await audit("studio-mobile-empty-history");
await capture("studio-mobile");
await page.goto("http://127.0.0.1:5174/plan");
await page.getByRole("heading", { name: "Review", exact: true }).waitFor();
await page.getByRole("button", { name: "Account menu" }).click();
await page.getByRole("menuitem", { name: "Sign out" }).click();
assert.equal(
  await page.evaluate(() =>
    Object.keys(sessionStorage).some((k) =>
      k.startsWith("roadtrips.setup.v1."),
    ),
  ),
  false,
);
await page.goto("http://127.0.0.1:5174/plan");
await page
  .getByRole("heading", { name: /Welcome back/i })
  .waitFor({ timeout: 5000 })
  .catch(() => {});
assert.equal(new URL(page.url()).pathname, "/login");
await fs.writeFile(
  out + "/browser-results.json",
  JSON.stringify(
    {
      scope:
        "Local intercepted API fixtures; no real providers, authentication verification or database writes",
      reports,
      requests: requests.map((r) => ({
        path: r.path,
        chatId: r.body.chatId ?? r.body.ChatData?.chatId,
      })),
      savedSnapshots: updates.length,
      errors,
    },
    null,
    2,
  ),
);
await browser.close();
console.log(
  JSON.stringify(
    {
      audits: reports.map((r) => ({
        name: r.name,
        violations: r.violations.length,
      })),
      errors,
      savedSnapshots: updates.length,
    },
    null,
    2,
  ),
);
assert.deepEqual(errors, []);
assert.equal(
  reports.every((r) => r.violations.length === 0),
  true,
  "Accessibility findings are recorded in browser-results.json",
);
