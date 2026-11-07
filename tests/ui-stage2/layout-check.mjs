// Browser presentation acceptance only. All HTTP providers are intercepted;
// this complements, and never replaces, the signed disposable-DB journey gate.
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
  process.env.ROADTRIPS_UI_EVIDENCE_DIR || "/tmp/roadtrips-ui-layout-evidence";
await mkdir(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  headless: true,
  args: ["--no-sandbox", "--disable-background-networking"],
});
const audits = [],
  errors = [],
  blocked = [],
  requests = [];
const baseline = process.env.UI_LAYOUT_BASELINE === "true";
const acceptance = {
  baseline,
  ordinary_no_scroll_assertions_enforced: !baseline,
};
let completed = false;
const routeData = {
  duration: 7200,
  distance: 150000,
  geometry: {
    type: "LineString",
    coordinates: [
      [-105.27, 40.01],
      [-104.99, 39.74],
      [-104.8, 39.9],
    ],
  },
};
async function inspectPanel(page, name, done, ordinary) {
  await done.waitFor({ state: "visible" });
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
    scrollY,
    outliers: [...document.querySelectorAll("body *")]
      .map((node) => ({ node, rect: node.getBoundingClientRect() }))
      .filter(
        ({ node, rect }) =>
          node.getClientRects().length &&
          rect.width &&
          (rect.right > innerWidth + 0.1 ||
            rect.bottom + scrollY > innerHeight + 2),
      )
      .map(({ node, rect }) => ({
        tag: node.tagName,
        cls: typeof node.className === "string" ? node.className : "svg",
        id: node.id,
        right: rect.right,
        bottom: rect.bottom + scrollY,
      }))
      .sort((a, b) => b.bottom - a.bottom)
      .slice(0, 20),
    scrollContainers: [...document.querySelectorAll("*")]
      .filter(
        (node) =>
          node.getClientRects().length &&
          /auto|scroll/.test(getComputedStyle(node).overflowY) &&
          node.scrollHeight > node.clientHeight + 2,
      )
      .map((node) => ({
        className: node.className,
        clientHeight: node.clientHeight,
        scrollHeight: node.scrollHeight,
      })),
  }));
  audits.push({ name, ...metrics });
  await page.screenshot({ path: join(out, name + ".png"), fullPage: true });
  assert.ok(
    metrics.scrollWidth <= metrics.width,
    name + " horizontal overflow",
  );
  if (ordinary && !baseline) {
    assert.ok(
      metrics.scrollHeight <= metrics.height + 2,
      name + " document scrolling",
    );
    assert.deepEqual(metrics.scrollContainers, [], name + " nested scrolling");
    const box = await done.boundingBox();
    assert.ok(
      box.y >= 0 && box.y + box.height <= metrics.height,
      name + " return action visible",
    );
  }
  await done.focus();
  assert.equal(
    await done.evaluate((node) => node === document.activeElement),
    true,
    name + " return action keyboard focus",
  );
}
try {
  for (const [width, height, scale] of [
    [390, 844, 1],
    [375, 812, 1],
    [1440, 900, 1],
    [320, 568, 1],
    [390, 844, 2],
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
                sub: "ui-layout",
                token_use: use,
                exp: Date.now() / 1000 + 3600,
              }),
            ) +
            ".fixture",
        );
      Object.defineProperty(navigator, "geolocation", {
        value: {
          getCurrentPosition() {
            throw Error("Location forbidden in presentation acceptance");
          },
          watchPosition() {
            throw Error("Location forbidden in presentation acceptance");
          },
          clearWatch() {},
        },
      });
    });
    let preferenceRows = [];
    await context.route("**/*", async (route) => {
      const url = new URL(route.request().url());
      if (url.origin === frontend) return route.continue();
      if (url.origin !== backend) {
        blocked.push(url.origin);
        return route.abort();
      }
      requests.push(url.pathname);
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
      const data =
        url.pathname === "/preference-profiles"
          ? preferenceRows
          : ["/chats", "/shared-trips"].includes(url.pathname)
            ? []
            : url.pathname === "/routing-settings"
              ? {
                  can_select_algorithm: false,
                  expires_at: Date.now() / 1000 + 3600,
                }
              : url.pathname === "/validate-location"
                ? {
                    address: JSON.parse(route.request().postData()).location
                      .address,
                    latitude: 40.01,
                    longitude: -105.27,
                  }
                : url.pathname === "/get-initial-route"
                  ? routeData
                  : null;
      if (data === null) throw Error("Unexpected fixture API: " + url.pathname);
      return route.fulfill({
        json: data,
        headers: { "access-control-allow-origin": "*" },
      });
    });
    const page = await context.newPage();
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(frontend + "/plan");
    await page
      .getByLabel("Starting city or address", { exact: true })
      .waitFor();
    await page.evaluate(() => {
      const key = "roadtrips.setup.v1.fixture%3Aui-layout";
      const state = JSON.parse(sessionStorage.getItem(key));
      Object.assign(state.draft, {
        start: "Boulder",
        destination: "Denver",
        date: "2027-06-01",
        carStatus: "provided",
        year: "2020",
        make: "Toyota",
        model: "Corolla",
      });
      sessionStorage.setItem(key, JSON.stringify(state));
    });
    await page.reload();
    await page
      .getByLabel("Starting city or address", { exact: true })
      .waitFor();
    if (scale === 2) {
      await page.addStyleTag({ content: "html{font-size:200% !important}" });
      await page.locator(".setup-design--large-text").waitFor();
    }
    await page
      .getByRole("button", { name: "Estimate driving time", exact: true })
      .click();
    await page.getByText(/hours driving/).waitFor();
    for (let stage = 0; stage < 5; stage++) {
      if (stage) {
        await page.getByRole("button", { name: "Next", exact: true }).click();
        await page.waitForFunction(
          (previous) =>
            document.querySelector(".setup-section h2")?.textContent !==
            previous,
          audits.at(-1)?.heading,
        );
      }
      const metrics = await page.evaluate(() => {
        const rect = (node) => {
          const r = node.getBoundingClientRect();
          return { top: r.top, bottom: r.bottom, height: r.height };
        };
        const visible = (node) =>
          node.getClientRects().length &&
          getComputedStyle(node).visibility !== "hidden";
        const section = document.querySelector(".setup-section"),
          footer = document.querySelector(".setup-footer"),
          root = document.documentElement;
        return {
          heading: section.querySelector("h2").textContent,
          width: innerWidth,
          height: innerHeight,
          scrollWidth: root.scrollWidth,
          scrollHeight: root.scrollHeight,
          section: rect(section),
          footer: rect(footer),
          animation: getComputedStyle(section).animationName,
          scrollContainers: [...document.querySelectorAll("*")]
            .filter(
              (n) =>
                visible(n) &&
                /auto|scroll/.test(getComputedStyle(n).overflowY) &&
                n.scrollHeight > n.clientHeight + 2,
            )
            .map((n) => ({
              className: n.className,
              clientHeight: n.clientHeight,
              scrollHeight: n.scrollHeight,
            })),
        };
      });
      const name = `setup-${width}x${height}-${scale * 100}pct-stage${stage}`;
      audits.push({ name, ...metrics });
      await page.screenshot({ path: join(out, name + ".png"), fullPage: true });
      assert.ok(metrics.scrollWidth <= width, name + " horizontal overflow");
      assert.equal(
        metrics.animation,
        "none",
        name + " reduced-motion animation",
      );
      assert.ok(metrics.section.height > 100, name + " readable question area");
      const next = page.getByRole("button", {
        name: stage === 4 ? "Check trip options" : "Next",
        exact: true,
      });
      await next.focus();
      assert.equal(
        await next.evaluate((node) => node === document.activeElement),
        true,
        name + " keyboard focus",
      );
      if (scale === 1 && width >= 375 && !baseline) {
        assert.ok(
          metrics.scrollHeight <= height + 2,
          name + " document scrolling",
        );
        assert.deepEqual(
          metrics.scrollContainers,
          [],
          name + " nested scrolling",
        );
        assert.ok(
          metrics.footer.bottom <= height && metrics.footer.top >= 0,
          name + " footer visible without scrolling",
        );
      }
      if (stage === 0) {
        await page.locator(".setup-route-map > summary").click();
        const done = page.getByRole("button", {
          name: "Done viewing route",
          exact: true,
        });
        await inspectPanel(
          page,
          name + "-route",
          done,
          scale === 1 && width >= 375,
        );
        await done.click();
        assert.equal(
          await page
            .locator(".setup-route-map > summary")
            .evaluate((node) => node === document.activeElement),
          true,
          "route Done returns focus",
        );
      }
      if (stage === 2) {
        for (const label of ["Compare places", "Adjust amounts"]) {
          await page.getByText(label, { exact: true }).click();
          const done = page.getByRole("button", {
            name: "Done adjusting interests",
            exact: true,
          });
          await inspectPanel(
            page,
            name + "-" + label.replaceAll(" ", "-").toLowerCase(),
            done,
            scale === 1 && width >= 375,
          );
          if (label === "Compare places") {
            assert.equal(
              await page
                .locator('.setup-comparisons input[type="radio"]')
                .count(),
              5,
              "exactly five comparison answers, without duplicate place radios",
            );
            const firstPlace = page
              .locator('.setup-comparison-places input[type="radio"]')
              .first();
            await firstPlace.focus();
            await page.keyboard.press("Space");
            assert.equal(
              await firstPlace.isChecked(),
              true,
              "place card selects by keyboard",
            );
            await page
              .getByRole("radio", { name: "Either place", exact: true })
              .check();
            assert.equal(
              await firstPlace.isChecked(),
              false,
              "either choice clears place-card selection",
            );
          }
          await done.click();
          assert.equal(
            await page
              .getByText(label, { exact: true })
              .evaluate((node) => node === document.activeElement),
            true,
            "interest Done returns focus",
          );
        }
      }
    }
    if (scale === 1 && width >= 375) {
      preferenceRows = await page.evaluate(async () => {
        const key = "roadtrips.setup.v1.fixture%3Aui-layout";
        const state = JSON.parse(sessionStorage.getItem(key));
        state.step = 0;
        sessionStorage.setItem(key, JSON.stringify(state));
        const { choicesFromDraft } = await import(
          "/src/services/preferenceProfiles.js"
        );
        return [
          {
            id: "fixture-preference",
            name: "Weekend",
            choices: choicesFromDraft(state.draft),
          },
        ];
      });
      await page.reload();
      await page.getByText("Use saved preferences", { exact: true }).click();
      await inspectPanel(
        page,
        `setup-${width}x${height}-saved-preferences`,
        page.getByRole("button", {
          name: "Done choosing preferences",
          exact: true,
        }),
        true,
      );
      await page
        .getByLabel("Saved preferences", { exact: true })
        .selectOption("fixture-preference");
      await page
        .getByRole("button", { name: "Load preferences", exact: true })
        .click();
      await page
        .getByRole("status")
        .filter({ hasText: "Preferences loaded." })
        .waitFor();
      await inspectPanel(
        page,
        `setup-${width}x${height}-loaded-preferences`,
        page.getByRole("button", { name: "Next", exact: true }),
        true,
      );
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
      const kept = await page.evaluate(
        () =>
          JSON.parse(
            sessionStorage.getItem("roadtrips.setup.v1.fixture%3Aui-layout"),
          ).draft,
      );
      assert.equal(kept.carStatus, "provided");
      assert.equal(kept.make, "Toyota");
      assert.equal(kept.model, "Corolla");
    }
    await context.close();
  }
  assert.deepEqual(errors, [], "browser errors");
  assert.deepEqual(blocked, [], "unexpected external requests");
  completed = true;
  console.log(
    JSON.stringify({
      passed: !baseline,
      ...acceptance,
      screens: audits.length,
      out,
      errors,
      blocked,
    }),
  );
} finally {
  await writeFile(
    join(out, "layout-report.json"),
    JSON.stringify(
      {
        scope:
          "Intercepted browser presentation; no actual backend/auth/providers/database",
        passed: completed && !baseline,
        ...acceptance,
        audits,
        errors,
        blocked,
        requests,
      },
      null,
      2,
    ),
  );
  await browser.close();
}
