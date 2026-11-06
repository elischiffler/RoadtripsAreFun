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
  process.env.ROADTRIPS_UI_EVIDENCE_DIR || "/tmp/roadtrips-stage2-evidence";
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
const audits = [];
await page.route("**/*", async (route) => {
  const url = new URL(route.request().url());
  if (url.origin === "http://127.0.0.1:5187") return route.continue();
  if (url.origin !== "http://127.0.0.1:18999") {
    blocked.push(url.origin);
    return route.abort();
  }
  requests.push(url.pathname);
  const data =
    url.pathname === "/chats"
      ? []
      : url.pathname === "/routing-settings"
        ? { can_select_algorithm: false, expires_at: Date.now() / 1000 + 3600 }
        : {};
  await route.fulfill({
    json: data,
    headers: { "access-control-allow-origin": "*" },
  });
});
await page.goto("http://127.0.0.1:5187/plan");
await page.getByLabel("Starting city or address", { exact: true }).waitFor();
const initial = await page.evaluate(
  () =>
    JSON.parse(
      sessionStorage.getItem("roadtrips.setup.v1.fixture%3Aui-integration"),
    ).draft,
);
const valid = {
  ...initial,
  start: "Boulder",
  destination: "Denver",
  date: "2027-06-01",
  carStatus: "provided",
  year: "2020",
  make: "Toyota",
  model: "Corolla",
};
try {
  for (const [width, height, textScale] of [
    [390, 844, 1],
    [320, 568, 1],
    [1365, 900, 1],
    [390, 844, 2],
  ]) {
    await page.setViewportSize({ width, height });
    for (let step = 0; step < 5; step++) {
      await page.evaluate(
        ({ valid, step }) =>
          sessionStorage.setItem(
            "roadtrips.setup.v1.fixture%3Aui-integration",
            JSON.stringify({ version: 1, draft: valid, step }),
          ),
        { valid, step },
      );
      await page.reload();
      await page
        .getByRole("button", {
          name: step === 4 ? "Check locations" : "Next",
          exact: true,
        })
        .waitFor();
      await page.addStyleTag({
        content: `html {font-size:${textScale * 100}% !important}`,
      });
      if (textScale === 2)
        await page.locator(".setup-design--large-text").waitFor();
      const panelHeight = await page
        .locator(".setup-section")
        .evaluate((node) => node.getBoundingClientRect().height);
      assert.ok(panelHeight > 100, "Question panel must remain readable");
      const name = `setup-${width}x${height}-${textScale * 100}pct-stage${step}`;
      const result = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      const metrics = await page.evaluate(() => ({
        width: innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        height: innerHeight,
        scrollHeight: document.documentElement.scrollHeight,
        animation: getComputedStyle(document.querySelector(".setup-section"))
          .animationName,
      }));
      const next = page.getByRole("button", {
        name: step === 4 ? "Check locations" : "Next",
        exact: true,
      });
      await next.scrollIntoViewIfNeeded();
      assert.equal(await next.isVisible(), true);
      assert.equal(
        metrics.scrollWidth <= metrics.width,
        true,
        name + " horizontal overflow",
      );
      assert.equal(metrics.animation, "none", name + " reduced motion");
      const saved = await page.evaluate(
        () =>
          JSON.parse(
            sessionStorage.getItem(
              "roadtrips.setup.v1.fixture%3Aui-integration",
            ),
          ).draft,
      );
      assert.equal(saved.make, "Toyota");
      assert.equal(saved.model, "Corolla");
      assert.equal(saved.carStatus, "provided");
      audits.push({
        name,
        metrics,
        violations: result.violations.map(({ id, impact, nodes }) => ({
          id,
          impact,
          targets: nodes.map((n) => n.target),
        })),
      });
      await page.evaluate(() => scrollTo(0, 0));
      await page.screenshot({ path: join(out, name + ".png"), fullPage: true });
    }
  }
  await fs.writeFile(
    join(out, "report.json"),
    JSON.stringify({ audits, errors, requests, blocked }, null, 2),
  );
  assert.deepEqual(errors, []);
  assert.deepEqual(
    audits.flatMap((a) => a.violations),
    [],
  );
  console.log(
    JSON.stringify({
      screens: audits.length,
      errors,
      violations: audits.flatMap((a) => a.violations),
      out,
    }),
  );
} finally {
  await browser.close();
}
