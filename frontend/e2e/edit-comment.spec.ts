import { test, expect } from "@playwright/test";
import { createDatabase } from "./fixtures";
test("edit own comment preserves file and edited marker after reload", async ({ page }) => {
  const db = createDatabase();
  db.sessionId = "alex";
  db.comments = [
    {
      id: "edit1",
      taskId: "1",
      userId: "alex",
      text: "Исходный комментарий",
      createdAt: db.now,
      attachments: [
        {
          id: "1",
          fileName: "demo.txt",
          fileSize: 4,
          contentType: "text/plain",
          downloadUrl: "/api/comment-attachments/1/download/",
        },
      ],
    },
  ];
  await page.route("**/api/**", async (route) => {
    if (route.request().method() === "PATCH" && route.request().url().includes("comments")) {
      expect(route.request().postDataJSON()).toEqual({
        text: "Исправленный комментарий",
        originalText: "Исходный комментарий",
      });
      db.comments[0].text = "Исправленный комментарий";
      db.comments[0].editedAt = db.now;
      await route.fulfill({ json: { snapshot: db } });
    } else
      await route.fulfill({
        json: route.request().url().includes("bootstrap")
          ? db
          : { snapshot: db, notifications: [], colleagues: [], projects: [] },
      });
  });
  await page.goto("/projects/sipi/tasks/1");
  await page.getByRole("button", { name: "Редактировать комментарий", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Редактировать комментарий", exact: true });
  await dialog.getByLabel("Текст комментария", { exact: true }).fill("Исправленный комментарий");
  await dialog.getByRole("button", { name: "Сохранить комментарий", exact: true }).click();
  await expect(page.getByText("Исправленный комментарий", { exact: true })).toBeVisible();
  await expect(page.getByText(/Изменено ·/)).toBeVisible();
  await page.reload();
  await expect(page.getByText("Исправленный комментарий", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /demo.txt/ })).toBeVisible();
  await page.screenshot({ path: "../docs/evidence/109-edit-comment.png", fullPage: true });
});
