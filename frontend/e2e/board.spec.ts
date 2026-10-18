import { expect, test } from "@playwright/test";
import { createProject, register, seedTask, api } from "./helpers";

test("Django persists dragging, status changes, ordering, and rejects full columns", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1400 });
  await register(page);
  const pid = await createProject(page);
  const first = await seedTask(page, pid, "Первая задача");
  const second = await seedTask(page, pid, "Вторая задача");
  const third = await seedTask(page, pid, "Третья задача");
  await page.reload();
  await page.getByRole("button", { name: "Доска", exact: true }).click();
  const card = (id: string) => page.locator(`[data-task-id="${id}"]`);
  const column = (status: string) => page.locator(`.task-column[data-status="${status}"]`);
  await card(first).dragTo(column("in_progress"));
  await expect(column("in_progress").locator(`[data-task-id="${first}"]`)).toHaveCount(1);
  await page.reload();
  await expect(column("in_progress").locator(`[data-task-id="${first}"]`)).toHaveCount(1);
  await card(first).getByLabel("Изменить статус задачи «Первая задача»").click();
  await card(first).getByRole("menuitem", { name: "На проверке", exact: true }).click();
  await expect(column("in_review").locator(`[data-task-id="${first}"]`)).toHaveCount(1);
  await card(first).getByLabel("Изменить статус задачи «Первая задача»").click();
  await card(first).getByRole("menuitem", { name: "В работе", exact: true }).click();
  await page.getByLabel("Что нужно доработать?").fill("Уточнить первый сценарий.");
  await page.getByRole("button", { name: "Вернуть в работу", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await card(third).dragTo(card(second));
  await expect(column("todo").locator(".task-card").first()).toHaveAttribute("data-task-id", third);
  await page.reload();
  await expect(column("todo").locator(".task-card").first()).toHaveAttribute("data-task-id", third);
  const response = await api(
    page,
    `projects/${pid}/columns/in_progress`,
    { name: "В работе", limit: 1 },
    "PATCH",
  );
  expect(response.ok()).toBe(true);
  // The page still shows the old limit: only the server can reject this stale move.
  await card(second).dragTo(column("in_progress"));
  await expect(page.getByRole("alert").filter({ hasText: "нет места" })).toBeVisible();
  await expect(column("todo").locator(`[data-task-id="${second}"]`)).toHaveCount(1);
  await page.reload();
  await expect(column("todo").locator(`[data-task-id="${second}"]`)).toHaveCount(1);
});
