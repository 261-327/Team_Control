import { test, expect } from "@playwright/test";
import { createDatabase } from "./fixtures";
test.use({ video: "on" });
test("delete own discussion comment and assistant pair with confirmation", async ({ page }) => {
  const db = createDatabase();
  db.sessionId = "alex";
  db.comments = [
    { id: "109", taskId: "1", userId: "alex", text: "Мой тестовый комментарий", createdAt: db.now },
  ];
  let turns = [
    {
      id: "11111111-1111-4111-8111-111111111111",
      message: "Мой тестовый запрос",
      mode: "chat",
      status: "succeeded",
      reply: { text: "Тестовый ответ помощника" },
      attachments: [],
      error: "",
      createdAt: db.now,
      confirmedAt: "",
    },
  ];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === "DELETE" && path.includes("/comments/")) {
      db.comments = [];
      await route.fulfill({ json: { snapshot: db } });
    } else if (route.request().method() === "DELETE" && path.includes("/message")) {
      turns = [];
      await route.fulfill({ json: {} });
    } else if (path.includes("assistant"))
      await route.fulfill({
        json: {
          turns,
          pendingAttachments: [],
          capabilities: { chatReady: true, imagesReady: false, model: "demo" },
        },
      });
    else
      await route.fulfill({
        json: path.includes("bootstrap")
          ? db
          : { snapshot: db, notifications: [], colleagues: [], projects: [] },
      });
  });
  await page.goto("/projects/sipi/tasks/1");
  await page.getByRole("button", { name: "Удалить комментарий", exact: true }).click();
  const confirm = page.getByRole("dialog", { name: "Удалить свой комментарий?" });
  await expect(confirm).toBeVisible();
  await page.screenshot({ path: "../docs/evidence/109-delete-comment.png", fullPage: true });
  await confirm.getByRole("button", { name: "Удалить", exact: true }).click();
  await expect(page.getByText("Мой тестовый комментарий", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("Мой тестовый комментарий", { exact: true })).toHaveCount(0);
  await page
    .getByRole("button", { name: /Сипи AI/ })
    .last()
    .click();
  await page.getByRole("button", { name: "Удалить сообщение и ответ", exact: true }).click();
  const ai = page.getByRole("dialog", { name: "Удалить сообщение и ответ?" });
  await expect(ai).toBeVisible();
  await page.screenshot({ path: "../docs/evidence/109-delete-assistant.png", fullPage: true });
  await ai.getByRole("button", { name: "Удалить", exact: true }).click();
  await expect(page.getByText("Мой тестовый запрос", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Тестовый ответ помощника", { exact: true })).toHaveCount(0);
});
