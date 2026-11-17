import { test, expect } from "@playwright/test";
import { createDatabase } from "./fixtures";
import { projectStatistics } from "../src/lib/project-statistics";

test("statistics count unique tasks, multiple assignees, custom stages and deadline boundaries", () => {
  const db = createDatabase();
  db.tasks = db.tasks.filter((task) => task.projectId === "sipi").slice(0, 4);
  db.tasks[0] = {
    ...db.tasks[0],
    status: "done",
    deadlineAt: "2020-01-01T00:00:00Z",
    assigneeIds: ["alex", "maria", "alex"],
  };
  db.tasks[1] = {
    ...db.tasks[1],
    status: "column_123",
    deadlineAt: "2020-01-01T00:00:00Z",
    assigneeId: "",
    assigneeIds: [],
  };
  db.tasks[2] = { ...db.tasks[2], status: "todo", deadlineAt: db.now };
  db.tasks[3] = { ...db.tasks[3], status: "in_progress", deadlineAt: "" };
  const stats = projectStatistics(db, "sipi");
  expect(stats.total).toBe(4);
  expect(stats.completed).toBe(1);
  expect(stats.overdue).toBe(1);
  expect(stats.withoutDeadline).toBe(1);
  expect(stats.completionPercent).toBe(25);
  expect(stats.unassigned.total).toBe(1);
  expect(stats.statuses.reduce((sum, row) => sum + row.count, 0)).toBe(4);
  expect(stats.members.find((member) => member.userId === "alex")?.completed).toBe(1);
  expect(stats.members.find((member) => member.userId === "maria")?.completed).toBe(1);
  db.tasks = [];
  expect(projectStatistics(db, "sipi").completionPercent).toBe(0);
});

test.use({ video: "on" });
test("project statistics render and update on desktop and mobile", async ({ page }) => {
  const db = createDatabase();
  db.sessionId = "alex";
  await page.route("**/api/**", async (route) => {
    await route.fulfill({
      json: route.request().url().includes("bootstrap")
        ? db
        : { notifications: [], colleagues: [], projects: [] },
    });
  });
  await page.goto("/projects/sipi/statistics");
  await expect(page.getByRole("heading", { name: "Статистика задач", exact: true })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await page.screenshot({ path: "../docs/evidence/111-statistics-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { name: "Статистика задач", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({ path: "../docs/evidence/111-statistics-mobile.png", fullPage: true });
  db.tasks = db.tasks.filter((task) => task.projectId !== "sipi");
  await page.reload();
  await expect(
    page.getByText("В проекте пока нет задач. Все показатели равны нулю."),
  ).toBeVisible();
  db.projects = [];
  await page.reload();
  await expect(page.getByRole("heading", { name: "Проект недоступен", exact: true })).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);
});
