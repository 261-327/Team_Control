import { expect, test } from "@playwright/test";
import { createDatabase } from "./fixtures";

test.use({ video: "on" });

test("custom developer direction is submitted by the shared project form", async ({ page }) => {
  const db = createDatabase();
  db.sessionId = "alex";
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.replace(/\/$/, "") === "/api/projects" && route.request().method() === "POST") {
      expect(route.request().postDataJSON().role.specialization).toBe("Разработка игр");
      await route.fulfill({
        status: 400,
        json: { error: { code: "validation", message: "Тестовый ответ: запрос проверен" } },
      });
    } else {
      await route.fulfill({
        json: path.includes("bootstrap") ? db : { notifications: [], colleagues: [], projects: [] },
      });
    }
  });
  await page.goto("/projects/new");
  await page.getByLabel("Название проекта").fill("Проверка своего направления");
  await page.getByLabel("Направление разработки", { exact: true }).selectOption("__custom__");
  const input = page.getByLabel("Своё направление разработки", { exact: true });
  await input.fill("   ");
  expect(await input.evaluate((element: HTMLInputElement) => element.checkValidity())).toBe(false);
  await input.fill("Разработка игр");
  await expect(input).toHaveAttribute("maxlength", "100");
  await page.screenshot({ path: "../docs/evidence/103-custom-direction.png", fullPage: true });
  await page.getByRole("button", { name: "Создать проект", exact: true }).click();
  await expect(page.getByText("Тестовый ответ: запрос проверен")).toBeVisible();
  await page.getByLabel("Направление разработки", { exact: true }).selectOption("backend");
  await expect(input).toHaveCount(0);
});
