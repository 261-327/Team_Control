import { test, expect } from "@playwright/test";
import { createDatabase } from "./fixtures";
test.use({ video: "on" });
test("file belongs to sent comment and survives reload", async ({ page }) => {
  const db = createDatabase();
  db.sessionId = "alex";
  db.comments = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.includes("/comments/files")) {
      expect(route.request().postDataBuffer()?.toString()).toContain("demo.txt");
      db.comments.push({
        id: "113",
        taskId: "1",
        userId: "alex",
        text: "Комментарий с файлом",
        createdAt: db.now,
        attachments: [
          {
            id: "113",
            fileName: "demo.txt",
            fileSize: 4,
            contentType: "text/plain",
            downloadUrl: "/api/comment-attachments/113/download/",
          },
        ],
      });
      await route.fulfill({ json: { commentId: "113", snapshot: db } });
    } else
      await route.fulfill({
        json: path.includes("bootstrap")
          ? db
          : { snapshot: db, notifications: [], colleagues: [], projects: [] },
      });
  });
  await page.goto("/projects/sipi/tasks/1");
  const file = page.locator('input[type="file"]').last();
  await file.setInputFiles({
    name: "demo.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("demo"),
  });
  await expect(
    page.getByRole("button", { name: "Просмотреть вложение", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Убрать вложение", exact: true }).click();
  await expect(page.getByRole("button", { name: "Убрать вложение", exact: true })).toHaveCount(0);
  await file.setInputFiles({
    name: "demo.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("demo"),
  });
  await page.getByLabel("Твой комментарий", { exact: true }).fill("Комментарий с файлом");
  await page.getByRole("button", { name: "Отправить", exact: true }).click();
  await expect(page.getByRole("link", { name: /demo.txt/ })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: /demo.txt/ })).toHaveAttribute(
    "href",
    "/api/comment-attachments/113/download/",
  );
  await page.screenshot({ path: "../docs/evidence/113-comment-file.png", fullPage: true });
});
