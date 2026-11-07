// Actual auth forms and SDK wire protocol with intercepted synthetic replies.
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
  process.env.ROADTRIPS_UI_EVIDENCE_DIR || "/tmp/roadtrips-ui-auth-evidence";
await mkdir(out, { recursive: true });
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  headless: true,
  args: ["--no-sandbox", "--disable-background-networking"],
});
const audits = [],
  errors = [],
  blocked = [],
  operations = [];
try {
  for (const width of [390, 1440])
    for (const theme of ["light", "dark"]) {
      const context = await browser.newContext({
        viewport: { width, height: width === 390 ? 844 : 900 },
        reducedMotion: "reduce",
      });
      await context.addInitScript(
        (mode) => localStorage.setItem("roadtrips.theme", mode),
        theme,
      );
      await context.route("**/*", async (route) => {
        const url = new URL(route.request().url());
        if (url.origin === frontend) return route.continue();
        if (url.origin !== backend) {
          blocked.push(url.origin);
          return route.abort();
        }
        const operation = route
          .request()
          .headers()
          ["x-amz-target"]?.split(".")
          .at(-1);
        operations.push(operation);
        if (operation === "SignUp")
          return route.fulfill({
            json: {
              UserSub: "synthetic-signup",
              UserConfirmed: false,
              CodeDeliveryDetails: {
                Destination: "t***@example.test",
                DeliveryMedium: "EMAIL",
                AttributeName: "email",
              },
            },
          });
        if (operation === "ConfirmSignUp")
          return route.fulfill({
            status: 400,
            contentType: "application/x-amz-json-1.1",
            body: JSON.stringify({
              __type: "CodeMismatchException",
              message: "Synthetic invalid code",
            }),
          });
        throw Error("Unexpected auth fixture operation: " + operation);
      });
      const page = await context.newPage();
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(frontend + "/plan");
      await page
        .getByRole("heading", { name: "Plan your trip", exact: true })
        .waitFor();
      const capture = async (view) => {
        const metrics = await page.evaluate(() => ({
          width: innerWidth,
          height: innerHeight,
          scrollWidth: document.documentElement.scrollWidth,
          scrollHeight: document.documentElement.scrollHeight,
          theme: document.documentElement.dataset.theme,
          color: getComputedStyle(document.querySelector(".auth-container"))
            .color,
          background: getComputedStyle(
            document.querySelector(".auth-container"),
          ).backgroundColor,
        }));
        const name = `auth-${width}-${theme}-${view}`;
        assert.ok(metrics.scrollWidth <= width, name + " horizontal overflow");
        if (view === "login" || view === "confirmation-error")
          assert.ok(
            metrics.scrollHeight <= metrics.height + 2,
            name + " unexpected normal-height overflow",
          );
        assert.equal(metrics.theme, theme);
        audits.push({ name, ...metrics });
        await page.screenshot({
          path: join(out, name + ".png"),
          fullPage: true,
        });
      };
      await capture("login");
      await page.getByRole("link", { name: "Sign up", exact: true }).click();
      await page
        .getByRole("textbox", { name: /^Email/ })
        .fill("traveler@example.test");
      await page.getByLabel(/^Password\s*\*?$/).fill("Fixture-only1!");
      await page.getByLabel(/^Confirm Password\s*\*?$/).fill("different");
      await page.getByRole("button", { name: "Sign Up", exact: true }).click();
      await page
        .getByRole("alert")
        .filter({ hasText: "Passwords do not match." })
        .waitFor();
      await capture("signup-error");
      await page.getByLabel(/^Confirm Password\s*\*?$/).fill("Fixture-only1!");
      await page.getByRole("button", { name: "Sign Up", exact: true }).click();
      await page.getByRole("textbox", { name: /^Confirmation Code/ }).waitFor();
      assert.equal(
        await page.getByRole("textbox", { name: /^Email/ }).count(),
        0,
        "confirmation replaces credential fields",
      );
      await page
        .getByRole("textbox", { name: /^Confirmation Code/ })
        .fill("123456");
      await page
        .getByRole("button", { name: "Confirm Account", exact: true })
        .click();
      await page
        .getByRole("alert")
        .filter({ hasText: "Code could not be confirmed." })
        .waitFor();
      await capture("confirmation-error");
      await page.getByRole("link", { name: "Sign in", exact: true }).click();
      await page
        .getByRole("heading", { name: "Plan your trip", exact: true })
        .waitFor();
      await context.close();
    }
  assert.deepEqual(errors, []);
  assert.deepEqual(blocked, []);
  assert.equal(
    operations.length,
    8,
    "only one signup and one invalid confirmation per case",
  );
  console.log(
    JSON.stringify({
      screens: audits.length,
      operations,
      errors,
      blocked,
      out,
    }),
  );
} finally {
  await writeFile(
    join(out, "auth-report.json"),
    JSON.stringify(
      {
        scope:
          "Actual auth presentation and SDK with synthetic intercepted responses; no real account created",
        audits,
        errors,
        blocked,
        operations,
      },
      null,
      2,
    ),
  );
  await browser.close();
}
