// Local UI fixture only. Start the isolated Vite instance described in the removal record.
import assert from "node:assert/strict";
const { chromium } = await import(
  process.env.PLAYWRIGHT_MODULE || "playwright"
);
import { writeFileSync } from "node:fs";

const browser = await chromium.launch({
  executablePath: "/usr/bin/chromium",
  headless: true,
  args: ["--no-sandbox"],
});
const context = await browser.newContext({
  viewport: { width: 1365, height: 900 },
});
const page = await context.newPage();
const errors = [];
const requests = [];
page.on("pageerror", (error) => errors.push(error.message));
await context.addInitScript(() => {
  if (!sessionStorage.getItem("accessToken")) {
    const token = (use) =>
      `e30.${btoa(JSON.stringify({ sub: "removal-fixture", iss: "fixture", token_use: use, exp: Date.now() / 1000 + 3600, iat: Date.now() / 1000 }))}.fixture`;
    sessionStorage.setItem("accessToken", token("access"));
    sessionStorage.setItem("idToken", token("id"));
  }
});
const route = {
  geometry: {
    coordinates: [
      [-105.27, 40.01],
      [-105.1, 39.9],
      [-104.99, 39.74],
    ],
  },
  duration: 7200,
  distance: 160000,
  stops: [],
  waypoints: [],
};
const trip = {
  chatId: 7,
  startConfirmed: {
    address: "Boulder, Colorado",
    latitude: 40.01,
    longitude: -105.27,
  },
  endConfirmed: {
    address: "Denver, Colorado",
    latitude: 39.74,
    longitude: -104.99,
  },
  route,
  itinerary: [
    {
      date: "Day 1",
      stops: [
        {
          name: "Fixture destination",
          time: "11:00 AM",
          address: "Denver, Colorado",
        },
      ],
    },
  ],
  agentChatId: "historical-id",
  tripProfile: {},
};
await page.route("http://127.0.0.1:18999/**", async (intercepted) => {
  const path = new URL(intercepted.request().url()).pathname;
  requests.push({ path, method: intercepted.request().method() });
  if (path === "/chats")
    return intercepted.fulfill({
      json: [
        [
          trip,
          {
            id: 7,
            title: "Fixture saved trip",
            messages: [
              { text: "Historical message stays stored", sender: "bot" },
            ],
          },
        ],
      ],
    });
  return intercepted.fulfill({
    status: 503,
    json: { detail: "No live providers in this fixture" },
  });
});
await page.goto("http://127.0.0.1:5179/");
await page.getByRole("link", { name: "Saved trips", exact: true }).click();
await page.getByText("Fixture saved trip", { exact: true }).waitFor();
assert.equal(new URL(page.url()).pathname, "/trips");
assert.equal(
  await page.getByText("Historical message stays stored").count(),
  0,
);
assert.equal(await page.getByRole("textbox").count(), 0);
await page.screenshot({
  path: "/tmp/journeygenie-saved-trips-desktop.png",
  fullPage: true,
});
await page.getByRole("link", { name: "View map", exact: true }).click();
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
await page.getByRole("link", { name: "Saved trips" }).first().click();
await page.getByText("Fixture saved trip", { exact: true }).waitFor();
await page.getByRole("link", { name: "View itinerary", exact: true }).click();
await page.getByText("Fixture destination", { exact: true }).waitFor();
await page.reload();
await page.getByText("Fixture destination", { exact: true }).waitFor();
await page.goto("http://127.0.0.1:5179/chat");
await page.getByText("Fixture saved trip", { exact: true }).waitFor();
assert.equal(new URL(page.url()).pathname, "/trips");
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({
  path: "/tmp/journeygenie-saved-trips-mobile.png",
  fullPage: true,
});
assert.ok(
  await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  "No horizontal overflow",
);
await page.getByRole("link", { name: "Plan a trip in Studio" }).click();
await page.getByLabel("Password", { exact: true }).waitFor();
assert.equal(new URL(page.url()).pathname, "/studio");
assert.deepEqual(errors, []);
assert.ok(requests.every((r) => !r.path.startsWith("/agent/")));
assert.ok(requests.every((r) => r.method === "GET"));
writeFileSync(
  "/tmp/journeygenie-browser-evidence.json",
  JSON.stringify(
    {
      passed: true,
      checks: [
        "saved-trip list without message/composer",
        "map selection and reload",
        "itinerary selection and reload",
        "old bookmark redirect",
        "mobile overflow",
        "Studio navigation",
        "no conversation requests or writes",
        "no page errors",
      ],
      requests,
      errors,
      fixtures:
        "Local intercepted saved trip, synthetic UI tokens and SVG map; no live providers, authentication verification or database writes",
    },
    null,
    2,
  ),
);
await browser.close();
console.log(
  "PASS: saved trips, map/itinerary reloads, bookmark redirect, mobile, Studio navigation; no chat calls/writes/page errors",
);
