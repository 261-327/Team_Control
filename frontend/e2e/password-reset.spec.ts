import { expect, test } from "@playwright/test";
import { mailCode, mailPasswordResetLink, register } from "./helpers";

test("password reset requires the emailed token and then regular OTP login", async ({ page }) => {
  const person = await register(page);
  await page.goto("/login");
  await page.getByRole("link", { name: "Забыли пароль?" }).click();
  await expect(page).toHaveURL(/forgot-password$/);
  await page.getByLabel("Электронная почта").fill(person.email);
  await page.getByRole("button", { name: "Отправить ссылку" }).click();
  await expect(page.getByRole("status")).toContainText("Если аккаунт с такой подтверждённой почтой существует");
  const resetLink = await mailPasswordResetLink(person.email);
  const resetUrl = new URL(resetLink);
  await page.goto(resetUrl.pathname + resetUrl.search);
  await expect(page.getByRole("heading", { name: "Новый пароль" })).toBeVisible();
  const newPassword = "Fresh-Browser-Password-942!";
  await page.getByLabel("Новый пароль").fill(newPassword);
  await page.getByLabel("Повтори новый пароль").fill(newPassword);
  await page.getByRole("button", { name: "Сменить пароль" }).click();
  await expect(page.getByRole("status")).toContainText("войдите с новым паролем");
  await page.getByRole("link", { name: "Перейти ко входу" }).click();
  await page.getByLabel("Логин или почта").fill(person.username);
  await page.getByLabel("Пароль").fill(newPassword);
  await page.getByRole("button", { name: "Продолжить" }).click();
  await expect(page.getByLabel("Шестизначный код")).toBeVisible();
  await page.getByLabel("Шестизначный код").fill(await mailCode(person.email));
  await page.getByRole("button", { name: "Подтвердить и войти" }).click();
  await expect(page).toHaveURL(/my-tasks$/);
}
