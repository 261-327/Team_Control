import { test, expect } from "@playwright/test";
import { createDatabase } from "./fixtures";
test.use({ video: "on" });

test("profile email change requires owner password and new-address confirmation", async ({
  page,
}) => {
  const db = createDatabase();
  db.sessionId = "alex";
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/$/, "");
    if (path.endsWith("profile/email-change/confirm")) {
      expect(route.request().postDataJSON()).toEqual({ code: "123456" });
      await route.fulfill({ json: { snapshot: { ...db, sessionId: null } } });
    } else if (path.endsWith("profile/email-change")) {
      expect(route.request().postDataJSON()).toEqual({
        email: "new@example.test",
        password: "Demo-only-password",
      });
      await route.fulfill({
        json: {
          expiresAt: new Date(Date.now() + 300000).toISOString(),
          resendAt: new Date(Date.now() + 60000).toISOString(),
        },
      });
    } else {
      await route.fulfill({
        json: path.endsWith("bootstrap") ? db : { colleagues: [], projects: [], notifications: [] },
      });
    }
  });
  await page.goto("/profile");
  await page.getByRole("button", { name: "Изменить почту", exact: true }).click();
  await page.getByLabel("Новая электронная почта", { exact: true }).fill("new@example.test");
  await page.getByLabel("Текущий пароль", { exact: true }).fill("Demo-only-password");
  await page.getByRole("button", { name: "Получить код", exact: true }).click();
  await expect(page.getByLabel("Код подтверждения новой почты")).toBeVisible();
  await expect(page.getByText("Проверь новый почтовый ящик. Код действует 5 минут.")).toBeVisible();
  await page.screenshot({ path: "../docs/evidence/100-email-confirm.png", fullPage: true });
  await page.getByLabel("Код подтверждения новой почты").fill("123456");
  await page.getByRole("button", { name: "Подтвердить новую почту", exact: true }).click();
  await expect(page).toHaveURL(/login$/);
});
