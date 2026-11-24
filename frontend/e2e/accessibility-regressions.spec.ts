import { expect, test, type Page } from "@playwright/test";
import { source } from "axe-core";
import { createDatabase } from "./fixtures";

async function workspace(page: Page) {
  const db = createDatabase();
  db.sessionId = "alex";
  db.projects = db.projects.filter((p) => p.id !== "robotics");
  await page.route("**/api/**", (route) =>
    route.fulfill({
      json: new URL(route.request().url()).pathname.includes("bootstrap")
        ? db
        : {
            notifications: [],
            colleagues: [],
            projects: [],
            turns: [],
            capabilities: { chatReady: true, local: false },
          },
    }),
  );
  await page.emulateMedia({ reducedMotion: "reduce" });
  return db;
}
const routes = ["/login", "/my-tasks", "/projects/sipi", "/calendar", "/profile", "/assistant"];

for (const theme of ["light", "dark"]) {
  test(`text contrast on principal screens in ${theme} theme`, async ({ page }) => {
    const db = await workspace(page);
    await page.addInitScript((value) => localStorage.setItem("sipi-theme", value), theme);
    for (const route of routes) {
      db.sessionId = route === "/login" ? null : "alex";
      await page.goto(route === "/assistant" ? "/my-tasks" : route);
      await page.getByRole("heading").first().waitFor();
      await expect(page.locator(".page-loading")).toHaveCount(0);
      await expect(page.getByText("Не удалось открыть страницу", { exact: true })).toHaveCount(0);
      if (route === "/assistant") await page.locator(".assistant-launcher").click();
      for (const input of await page.locator(".search-field input").all()) {
        await expect(input).toHaveCSS("border-top-width", "0px");
      }
      await page.addScriptTag({ content: source });
      const violations = await page.evaluate(async () => {
        const axe = (window as unknown as { axe: typeof import("axe-core") }).axe;
        return (await axe.run({ runOnly: ["color-contrast"] })).violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => ({ target: n.target, reason: n.failureSummary })),
        }));
      });
      expect(violations, `${theme} ${route}`).toEqual([]);
      if (route === "/projects/sipi")
        await page.screenshot({
          animations: "disabled",
          path: `../docs/evidence/backlog-contrast-${theme}.png`,
          fullPage: true,
        });
    }
  });
}

// 720 CSS px also checks reflow for a 1440 px window at 200% browser zoom.
// It does not emulate a physical iOS keyboard or certify all WCAG criteria.
for (const width of [320, 375, 720, 768, 1440]) {
  test(`principal screens reflow without page overflow at ${width}px`, async ({ page }) => {
    const db = await workspace(page);
    await page.setViewportSize({ width, height: 900 });
    for (const route of routes) {
      db.sessionId = route === "/login" ? null : "alex";
      await page.goto(route === "/assistant" ? "/my-tasks" : route);
      await page.getByRole("heading").first().waitFor();
      await expect(page.locator(".page-loading")).toHaveCount(0);
      await expect(page.getByText("Не удалось открыть страницу", { exact: true })).toHaveCount(0);
      if (route === "/assistant") await page.locator(".assistant-launcher").click();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
        route,
      ).toBe(true);
    }
  });
}
