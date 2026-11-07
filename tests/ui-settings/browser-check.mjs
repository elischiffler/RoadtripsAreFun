// Local intercepted fixtures only. All non-local requests are aborted.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
const tools = process.env.UI_BROWSER_TOOLS_DIR || "/tmp/roadtrips-ui-browser";
const { chromium } = await import(pathToFileURL(join(tools, "node_modules/playwright-core/index.mjs")));
const { default: AxeBuilder } = await import(pathToFileURL(join(tools, "node_modules/@axe-core/playwright/dist/index.mjs")));
const out = process.env.ROADTRIPS_UI_EVIDENCE_DIR || "/tmp/roadtrips-settings-evidence";
const base = process.env.SETTINGS_UI_URL || "http://127.0.0.1:5189";
assert.equal(new URL(base).hostname, "127.0.0.1");
await fs.mkdir(out, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium", headless: true, args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: "reduce" });
await context.addInitScript(() => {
  for (const use of ["access", "id"]) sessionStorage.setItem(use + "Token", "header." + btoa(JSON.stringify({ iss: "fixture", sub: "settings-browser", token_use: use, exp: Date.now()/1000 + 3600 })) + ".fixture");
});
const page = await context.newPage(), errors = [], blocked = [], writes = [], audits = [];
page.setDefaultTimeout(15000);
page.on("pageerror", (error) => errors.push(error.message));
const keys = ["scenery","nature","hiking_outdoors","food","history","culture_arts","nightlife","shopping","beaches_water","adventure","relaxation","unique_local_experiences","family_friendliness","crowd_avoidance"];
const weights = Object.fromEntries(keys.map((key) => [key, 1/keys.length]));
const schedule = { morning_restart: "09:00", preferred_hotel_arrival: "18:00", latest_hotel_arrival: "20:00", latest_destination_arrival: "21:00", late_driving: false, late_cutoff: "24:00" };
let profiles = [{ id: "244ca737-10eb-4d60-8362-f57269348ca6", name: "Weekend", choices: { car_status: "skipped", car: null, scheduling_policy: schedule, persona_weights: weights } }];
const trip = { chatId: 4, agentChatId: "browser-trip", carDetails: ["2018","Toyota","Corolla"], tripProfile: null, carBudget: 50, stops: 3, route: null, itinerary: null };
await page.route("**/*", async (route) => {
  const request = route.request(), url = new URL(request.url());
  if (url.origin === base) return route.continue();
  if (url.origin !== "http://127.0.0.1:18999") { blocked.push(url.origin); return route.abort(); }
  const method = request.method();
  if (method === "OPTIONS") return route.fulfill({ status: 204, headers: { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "GET,PUT,DELETE,OPTIONS" } });
  let data;
  if (url.pathname === "/routing-settings") data = { can_select_algorithm: false, expires_at: Date.now()/1000 + 3600 };
  else if (url.pathname === "/chats") data = [[trip, { id: 4, title: "Boulder → Denver", messages: [] }]];
  else if (url.pathname === "/preference-profiles" && method === "GET") data = profiles;
  else if (url.pathname.startsWith("/preference-profiles/") && method === "PUT") {
    data = { id: url.pathname.split("/").at(-1), ...request.postDataJSON() };
    profiles = [...profiles.filter((item) => item.id !== data.id), data]; writes.push("profile-save");
  } else if (url.pathname.startsWith("/preference-profiles/") && method === "DELETE") {
    profiles = profiles.filter((item) => item.id !== url.pathname.split("/").at(-1)); writes.push("profile-delete");
    return route.fulfill({ status: 204, headers: { "access-control-allow-origin": "*" } });
  } else if (url.pathname === "/chats/4/car" && method === "PUT") {
    const { expected_agent_chat_id, ...choices } = request.postDataJSON();
    assert.equal(expected_agent_chat_id, "browser-trip");
    data = choices; trip.tripProfile = { ...trip.tripProfile, ...choices }; trip.carDetails = choices.car ? [String(choices.car.year), choices.car.make, choices.car.model] : ["","",""]; trip.carBudget = null; writes.push("trip-car-save");
  } else throw new Error("Unexpected fixture request: " + method + " " + url.pathname);
  return route.fulfill({ json: data, headers: { "access-control-allow-origin": "*" } });
});
try {
  console.log("Loading fixture settings");
  await page.goto(base + "/settings");
  await page.getByLabel("Car make", { exact: true }).waitFor();
  assert.equal(await page.getByLabel("Car make", { exact: true }).inputValue(), "Toyota");
  await page.getByLabel("Car make", { exact: true }).fill("Honda");
  await page.getByRole("button", { name: "Save trip car", exact: true }).click();
  await page.getByText("Trip car saved.", { exact: true }).waitFor();
  console.log("Trip car saved; checking reload");
  await page.getByRole("radio", { name: "Dark", exact: true }).check();
  await page.reload();
  await page.getByLabel("Car make", { exact: true }).waitFor();
  assert.equal(await page.getByLabel("Car make", { exact: true }).inputValue(), "Honda");
  assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
  console.log("Car/theme reload passed; checking profiles");
  const prefs = page.getByRole("region", { name: "Trip preferences", exact: true });
  await prefs.getByRole("button", { name: "New preferences", exact: true }).click();
  await prefs.getByLabel("Profile name").fill("Quiet weekends");
  await prefs.getByText("Interests", { exact: true }).click();
  await prefs.getByLabel("Quieter places").check();
  await prefs.getByRole("button", { name: "Save preferences", exact: true }).click();
  await prefs.getByText("Preferences saved.", { exact: true }).waitFor();
  await prefs.getByRole("button", { name: "Delete Weekend", exact: true }).click();
  await prefs.getByRole("button", { name: "Confirm delete", exact: true }).click();
  await prefs.getByText("Preferences deleted.", { exact: true }).waitFor();
  for (const [width,height,scale] of [[390,844,1],[320,568,1],[1365,900,1],[390,844,2]]) {
    await page.setViewportSize({ width, height });
    await page.evaluate((scale) => document.documentElement.style.fontSize = 16*scale + "px", scale);
    for (const theme of ["Light","Dark"]) {
      await page.getByRole("radio", { name: theme, exact: true }).check();
      await page.getByRole("button", { name: "Save trip car", exact: true }).scrollIntoViewIfNeeded();
      console.log("Auditing", width, height, scale, theme);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      const result = await new AxeBuilder({ page }).withTags(["wcag2a","wcag2aa"]).analyze();
      audits.push({ width, height, textScale: scale, theme, horizontalOverflow: overflow, violations: result.violations.map(({id,impact,nodes}) => ({ id, impact, targets: nodes.map((node) => node.target) })) });
      if (width === 390 && scale === 1) await page.screenshot({ path: join(out, "mobile-" + theme.toLowerCase() + ".png"), fullPage: true });
    }
  }
  await fs.writeFile(join(out,"browser-report.json"), JSON.stringify({ fixtureOnly: true, audits, errors, blockedExternalOrigins: [...new Set(blocked)], writes, legacyCarLoaded: true, carPersistedAcrossReload: true, themePersistedAcrossReload: true, profileCreatedAndDeleted: true }, null, 2));
  assert.equal(errors.length, 0);
  assert.equal(audits.some((audit) => audit.horizontalOverflow || audit.violations.length), false);
  assert.deepEqual(writes, ["trip-car-save","profile-save","profile-delete"]);
  console.log("Settings browser acceptance passed: 8 viewport/theme audits, legacy car/edit/reload, profile create/delete, theme persistence; zero axe violations or overflow.");
} finally { await browser.close(); }
