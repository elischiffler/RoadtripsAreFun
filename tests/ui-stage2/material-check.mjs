// Actual saved-trip controls and MUI dialog; synthetic read only, no delete call.
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
  process.env.ROADTRIPS_UI_EVIDENCE_DIR ||
  "/tmp/roadtrips-ui-material-evidence";
await mkdir(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  headless: true,
  args: ["--no-sandbox", "--disable-background-networking"],
});
const audits = [],
  errors = [],
  blocked = [];
try {
  for (const width of [390, 1440])
    for (const theme of ["light", "dark"]) {
      const context = await browser.newContext({
        viewport: { width, height: width === 390 ? 844 : 900 },
        reducedMotion: "reduce",
      });
      await context.addInitScript((mode) => {
        localStorage.setItem("roadtrips.theme", mode);
        for (const use of ["access", "id"])
          sessionStorage.setItem(
            use + "Token",
            "header." +
              btoa(
                JSON.stringify({
                  iss: "fixture",
                  sub: "ui-material",
                  token_use: use,
                  exp: Date.now() / 1000 + 3600,
                }),
              ) +
              ".fixture",
          );
      }, theme);
      await context.route("**/*", async (route) => {
        const url = new URL(route.request().url());
        if (url.origin === frontend) return route.continue();
        if (url.origin !== backend) {
          blocked.push(url.origin);
          return route.abort();
        }
        assert.equal(
          route.request().method(),
          "GET",
          "presentation lane must not write trip data",
        );
        const data =
          url.pathname === "/chats"
            ? [
                [
                  {
                    chatId: 4,
                    startConfirmed: { address: "Portland, OR" },
                    endConfirmed: { address: "Seattle, WA" },
                    tripProfile: { start_date: "2027-03-12" },
                    itinerary: [
                      { date: "2027-03-12", stops: [] },
                      { date: "2027-03-14", stops: [] },
                    ],
                  },
                  { id: 4, title: "Coastal trip", messages: [] },
                ],
              ]
            : url.pathname === "/routing-settings"
              ? {
                  can_select_algorithm: false,
                  expires_at: Date.now() / 1000 + 3600,
                }
              : [];
        return route.fulfill({ json: data });
      });
      const page = await context.newPage();
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(frontend + "/trips");
      await page
        .getByRole("heading", { name: "Coastal trip", exact: true })
        .waitFor();
      await page
        .getByText("Portland, OR → Seattle, WA", { exact: true })
        .waitFor();
      await page
        .getByText("2027-03-12 – 2027-03-14", { exact: true })
        .waitFor();
      const primary = await page
        .getByRole("main")
        .getByRole("link", { name: "Plan a trip", exact: true })
        .evaluate((node) => ({
          background: getComputedStyle(node).backgroundColor,
          height: node.getBoundingClientRect().height,
        }));
      await page
        .getByRole("button", { name: "Delete Coastal trip", exact: true })
        .click();
      await page.getByRole("dialog").waitFor();
      const metrics = await page.getByRole("dialog").evaluate((node) => {
        const resolve = (token) => {
          const probe = document.createElement("span");
          probe.style.color = `var(${token})`;
          document.querySelector(".rt-design").append(probe);
          const color = getComputedStyle(probe).color;
          probe.remove();
          return color;
        };
        const rect = node.getBoundingClientRect();
        return {
          width: innerWidth,
          scrollWidth: document.documentElement.scrollWidth,
          dialog: {
            left: rect.left,
            right: rect.right,
            top: rect.top,
            bottom: rect.bottom,
          },
          background: getComputedStyle(node).backgroundColor,
          color: getComputedStyle(node).color,
          accent: resolve("--rt-color-accent"),
          surface: resolve("--rt-color-surface"),
          text: resolve("--rt-color-text"),
        };
      });
      assert.equal(
        primary.background,
        metrics.accent,
        "MUI primary follows shared accent",
      );
      assert.ok(primary.height >= 44, "MUI primary has touch target");
      assert.equal(
        metrics.background,
        metrics.surface,
        "MUI dialog follows shared surface",
      );
      assert.equal(
        metrics.color,
        metrics.text,
        "MUI dialog follows shared text",
      );
      assert.ok(metrics.scrollWidth <= width);
      assert.ok(
        metrics.dialog.left >= 0 &&
          metrics.dialog.right <= width &&
          metrics.dialog.top >= 0 &&
          metrics.dialog.bottom <= (width === 390 ? 844 : 900),
      );
      const name = `material-${width}-${theme}-delete-dialog`;
      audits.push({ name, primary, ...metrics });
      await page.screenshot({ path: join(out, name + ".png"), fullPage: true });
      await page.getByRole("button", { name: "Cancel", exact: true }).click();
      await page
        .getByRole("heading", { name: "Coastal trip", exact: true })
        .waitFor();
      await context.close();
    }
  assert.deepEqual(errors, []);
  assert.deepEqual(blocked, []);
  console.log(JSON.stringify({ screens: audits.length, errors, blocked, out }));
} finally {
  await writeFile(
    join(out, "material-report.json"),
    JSON.stringify(
      {
        scope:
          "Actual MUI/saved-trip presentation with synthetic GET responses; no data writes or providers",
        audits,
        errors,
        blocked,
      },
      null,
      2,
    ),
  );
  await browser.close();
}
