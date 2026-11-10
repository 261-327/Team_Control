import { expect, test } from "@playwright/test";
import { api, bootstrap, createProject, register } from "./helpers";

for (const viewport of [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
]) {
  test(`overdue banner reveals and focuses the filtered task list at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await register(page);
    const projectId = await createProject(page);
    const assigneeId = (await bootstrap(page)).sessionId;
    for (const [title, days] of [
      ["Просроченная задача", -1],
      ["Будущая задача", 1],
    ] as const) {
      const response = await api(page, "tasks", {
        projectId,
        assigneeId,
        title,
        description: "Проверка перехода из плашки сроков",
        deadlineAt: new Date(Date.now() + days * 86400000).toISOString(),
        tag: "Команда",
      });
      expect(response.ok()).toBe(true);
    }
    await page.goto("/my-tasks");
    await page.getByRole("button", { name: "Завершённые", exact: true }).click();
    await page.getByLabel("Найти задачу", { exact: true }).fill("Не найдено");
    await page.getByRole("button", { name: "Посмотреть", exact: true }).click();

    const list = page.getByRole("region", { name: /^Задачи/ });
    const heading = list.getByRole("heading", { name: /^Задачи/ });
    await expect(heading).toBeFocused();
    await expect(heading).toBeInViewport();
    await expect(list.getByRole("link", { name: /Просроченная задача/ })).toBeVisible();
    await expect(list.getByRole("link", { name: /Будущая задача/ })).toHaveCount(0);
    await expect(page.getByLabel("Найти задачу", { exact: true })).toHaveValue("");

    await page.getByRole("button", { name: /^Открыто/ }).click();
    await expect(heading).toBeFocused();
    await expect(heading).toBeInViewport();
    await expect(list.getByRole("link", { name: /Будущая задача/ })).toBeVisible();
    await list.getByRole("link", { name: /Просроченная задача/ }).click();
    await expect(
      page.getByRole("heading", { name: "Просроченная задача", exact: true }),
    ).toBeVisible();
  });
}
