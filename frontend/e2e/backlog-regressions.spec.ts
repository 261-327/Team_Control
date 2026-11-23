import { expect, test, type Page } from "@playwright/test";
import { createDatabase } from "./fixtures";
import { isAssigned, allowedTransitions } from "../src/lib/permissions";
import { filterTasks, defaultFilters } from "../src/features/tasks/TaskViews";

async function mockWorkspace(page: Page, many = false) {
  const db = createDatabase();
  db.sessionId = "alex";
  db.projects = db.projects.filter((p) => p.id === "sipi" || p.id === "campus");
  if (many)
    db.tasks = Array.from({ length: 51 }, (_, i) => ({
      ...db.tasks[0],
      id: `test-${i}`,
      title: `Задача ${i}`,
      assigneeId: "maria",
      assigneeIds: ["maria", "alex"],
      status: i === 50 ? "done" : "todo",
    }));
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
  return db;
}

test("every assignee is included, filters intersect and foreign tasks stay inaccessible", () => {
  const db = createDatabase();
  db.sessionId = "alex";
  const task = {
    ...db.tasks[0],
    assigneeId: "maria",
    assigneeIds: ["maria", "alex"],
    status: "todo" as const,
  };
  expect(isAssigned(task, "alex")).toBe(true);
  expect(isAssigned(task, null)).toBe(false);
  expect(allowedTransitions(db, task)).toEqual(["in_progress"]);
  expect(allowedTransitions(db, { ...task, projectId: "robotics" })).toEqual([]);
  const snapshot = { ...db, connectionError: "" };
  expect(
    filterTasks([task], { ...defaultFilters, mine: true, status: "todo" }, snapshot),
  ).toHaveLength(1);
  expect(
    filterTasks([task], { ...defaultFilters, mine: true, status: "done" }, snapshot),
  ).toHaveLength(0);
  expect(
    filterTasks([task], { ...defaultFilters, assignee: "alex", query: "no match" }, snapshot),
  ).toHaveLength(0);
});

for (const width of [375, 1440]) {
  test(`active tasks, pagination, calendar date and headers at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockWorkspace(page, true);
    const response = await page.goto("/my-tasks");
    expect(response?.headers()["x-content-type-options"]).toBe("nosniff");
    expect(response?.headers()["x-frame-options"]).toBe("DENY");
    await page.getByRole("button", { name: "Активные", exact: true }).click();
    const list = page.getByRole("region", { name: /^Задачи/ });
    await expect(list.locator(".task-row")).toHaveCount(20);
    await expect(list.getByText("Показано 20 из 50")).toBeVisible();
    await list.getByRole("button", { name: "Показать ещё" }).click();
    await expect(list.locator(".task-row")).toHaveCount(40);
    await page.getByLabel("Найти задачу", { exact: true }).fill("Задача 49");
    await expect(list.locator(".task-row")).toHaveCount(1);
    await expect(list.getByText("Задача 49", { exact: true })).toBeVisible();
    await page.getByLabel("Найти задачу", { exact: true }).fill("");
    await page.getByRole("button", { name: "Завершённые", exact: true }).click();
    await expect(list.locator(".task-row")).toHaveCount(1);
    await page.goto("/calendar");
    await page.getByLabel("Перейти к дате", { exact: true }).fill("2028-02-29");
    await expect(page.getByRole("heading", { name: /Задачи на 29 фев/ })).toBeVisible();
    await expect(page.getByLabel("Перейти к дате", { exact: true })).toHaveValue("2028-02-29");
    await page.screenshot({
      animations: "disabled",
      path: `../docs/evidence/backlog-calendar-${width}.png`,
      fullPage: true,
    });
  });
}

test("search suggests only accessible projects and help close button stays visible", async ({
  page,
}) => {
  await mockWorkspace(page);
  await page.goto("/my-tasks");
  await page.getByRole("button", { name: "Поиск по пространству", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Найти в пространстве" });
  await expect(dialog.locator(".search-results a")).toHaveCount(2);
  await expect(dialog.getByText("Робототехника", { exact: true })).toHaveCount(0);
  await dialog.getByLabel("Поиск проектов и задач").fill("ничегонет");
  await expect(dialog.getByText("Ничего не нашлось")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.locator(".project-nav-toggle").click();
  await expect(page.locator("#sidebar-projects")).toBeHidden();
  await page.locator(".project-nav-toggle").click();
  await expect(page.locator("#sidebar-projects")).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 500 });
  await page.getByRole("button", { name: /Помощь и о проекте/ }).click();
  const help = page.getByRole("dialog", { name: "О Сипи" });
  await help.locator(".modal-body").evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await expect(help.getByRole("button", { name: "Закрыть", exact: true })).toBeInViewport();
  await page.screenshot({ animations: "disabled", path: "../docs/evidence/backlog-help.png" });
});

test("password visibility preserves value and does not submit the form", async ({ page }) => {
  await page.route("**/api/bootstrap", (route) => route.fulfill({ json: createDatabase() }));
  await page.goto("/login");
  const input = page.getByLabel("Пароль", { exact: true });
  await input.fill("Example-not-a-real-password!");
  await page.getByRole("button", { name: "Показать пароль", exact: true }).click();
  await expect(input).toHaveAttribute("type", "text");
  await expect(input).toHaveValue("Example-not-a-real-password!");
  await expect(page).toHaveURL(/\/login/);
  await page.getByRole("button", { name: "Скрыть пароль", exact: true }).click();
  await expect(input).toHaveAttribute("type", "password");
});

for (const width of [320, 375, 768, 1440]) {
  test(`long projects and assistant stay usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const db = await mockWorkspace(page);
    db.projects[0].name = "Длинноеназваниебезпробелов".repeat(12);
    db.projects[0].description = "Описание проекта ".repeat(80);
    await page.goto("/projects");
    await expect(page.locator(".project-mini-card").first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(
      true,
    );
    const title = page.locator(".project-mini-card h3").first();
    expect(await title.evaluate((el) => el.getBoundingClientRect().height)).toBeLessThan(70);
    await page.screenshot({
      animations: "disabled",
      path: `../docs/evidence/backlog-projects-${width}.png`,
      fullPage: true,
    });
    await page.locator(".assistant-launcher").click();
    const chat = page.getByRole("dialog");
    const input = chat.getByLabel("Сообщение помощнику", { exact: true });
    await expect(input).toBeVisible();
    await input.fill("Помоги разобраться с проектом");
    await expect(
      chat.getByRole("button", { name: "Отправить сообщение", exact: true }),
    ).toBeEnabled();
    if (width <= 375) {
      await page.setViewportSize({ width, height: 500 });
      await expect(input).toBeInViewport();
      await expect(
        chat.getByRole("button", { name: "Отправить сообщение", exact: true }),
      ).toBeInViewport();
    }
    await expect(chat.locator(".assistant-help")).not.toHaveAttribute("open", "");
    await page.screenshot({
      animations: "disabled",
      path: `../docs/evidence/backlog-assistant-${width}.png`,
    });
  });
}

test("required-field messages are Russian and clear after editing", async ({ page }) => {
  await page.route("**/api/bootstrap", (route) => route.fulfill({ json: createDatabase() }));
  await page.goto("/login");
  const password = page.getByLabel("Пароль", { exact: true });
  await page.getByRole("button", { name: "Продолжить", exact: true }).click();
  expect(await password.evaluate((el: HTMLInputElement) => el.validationMessage)).toBe(
    "Заполни это поле.",
  );
  await password.fill("Example-password-42!");
  expect(await password.evaluate((el: HTMLInputElement) => el.validationMessage)).toBe("");
});

test("calendar and list share status colors and completed tasks are never overdue", async ({
  page,
}) => {
  const db = await mockWorkspace(page);
  db.tasks = (["todo", "in_progress", "in_review", "done"] as const).map((status, i) => ({
    ...db.tasks[0],
    id: `status-${i}`,
    status,
    assigneeId: "alex",
    assigneeIds: ["alex"],
    deadlineAt: `2026-10-${12 + i}T18:00:00+03:00`,
  }));
  await page.goto("/calendar");
  for (const status of ["todo", "in_progress", "in_review", "done"]) {
    const card = page.locator(`.calendar-task.status-${status}`);
    const badge = page.locator(`.status-badge.status-${status}`);
    await expect(card).toBeVisible();
    await expect(badge).toBeVisible();
    expect(await card.evaluate((el) => getComputedStyle(el).color)).toBe(
      await badge.evaluate((el) => getComputedStyle(el).color),
    );
  }
  await expect(page.locator(".calendar-task.status-done")).not.toHaveClass(/deadline-overdue/);
  await expect(page.locator(".calendar-task.status-todo")).toContainText("Просрочено");
  await page.getByLabel("Срок", { exact: true }).selectOption("overdue");
  await expect(page.locator(".calendar-task.status-done")).toHaveCount(0);
  await expect(page.locator(".calendar-task")).toHaveCount(3);
});

for (const width of [375, 1440]) {
  test(`home navigation and project creation have working unambiguous entry points at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const db = await mockWorkspace(page);
    await page.goto("/projects");
    const home = page.getByRole("link", { name: "На главную: мои задачи" });
    await expect(home).toBeVisible();
    await home.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/my-tasks$/);
    db.projects = [];
    db.memberships = [];
    db.tasks = [];
    await page.goto("/projects");
    await expect(page.locator(".page-heading a[href='/projects/new']")).toHaveCount(0);
    const create = page.locator(".project-create-placeholder");
    await expect(create).toBeVisible();
    await create.click();
    await expect(page).toHaveURL(/projects\/new$/);
  });
}
