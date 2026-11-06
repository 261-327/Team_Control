import { expect, test } from "@playwright/test";
import { createProject, register, seedTask, api, bootstrap } from "./helpers";

test("Task lifecycle: submit, review, accept, reset, resubmit with new URL", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1400 });
  await register(page);
  const pid = await createProject(page);
  const taskId = await seedTask(page, pid, "Тестовая задача с циклом");
  await page.reload();

  // Открываем карточку задачи
  await page.goto(`/projects/${pid}/tasks/${taskId}`);
  await expect(page.locator(".task-detail-page")).toBeVisible();

  // 1. К выполнению → В работе
  const submitToReviewBtn = page.getByRole("button", { name: "Начать работу" });
  await expect(submitToReviewBtn).toBeVisible();
  await submitToReviewBtn.click();
  await expect(page.getByRole("status").filter({ hasText: /в работе|работе/i })).toBeVisible({ timeout: 10000 });

  // 2. В работе → На проверку (с resultUrl)
  const resultInput = page.locator("input[type='url'][placeholder='https://…']");
  await expect(resultInput).toBeVisible();
  await resultInput.fill("https://github.com/test-repo/pr-1");
  await page.getByRole("button", { name: "Отправить на проверку" }).click();
  await expect(page.getByRole("status").filter({ hasText: /проверке|review/i })).toBeVisible({ timeout: 10000 });

  // Проверим, что URL виден в секции результата
  const resultLink = page.locator(".task-result a.result-link");
  await expect(resultLink).toBeVisible();
  await expect(resultLink).toContainText("github.com/test-repo/pr-1");

  // 3. На проверке → Готово (принять результат)
  const acceptBtn = page.getByRole("button", { name: "Принять результат" });
  await expect(acceptBtn).toBeVisible();
  await acceptBtn.click();
  await expect(page.getByText("Результат принят")).toBeVisible({ timeout: 10000 });

  // Проверим, что resultUrl всё ещё виден в статусе done
  await expect(resultLink).toBeVisible();
  await expect(resultLink).toContainText("github.com/test-repo/pr-1");

  // 4. Готово → К выполнению (сброс)
  // Для этого нам нужно через API сбросить задачу
  const resetResponse = await api(page, `tasks/${taskId}/move`, { status: "todo" });
  expect(resetResponse.ok()).toBe(true);

  // Перезагружаем страницу
  await page.reload();

  // 5. Проверяем, что resultUrl НЕ отображается в статусе todo
  const taskResultSection = page.locator(".task-result");
  // В режиме todo секция result может быть видна только для формы "Следующий шаг",
  // но старая ссылка result-link не должна быть видна
  await expect(taskResultSection.locator("a.result-link")).toHaveCount(0);

  // 6. В работе → На проверку с НОВЫМ URL
  await page.getByRole("button", { name: "Начать работу" }).click();
  await expect(page.getByRole("status").filter({ hasText: /в работе|работе/i })).toBeVisible({ timeout: 10000 });

  const newResultInput = page.locator("input[type='url'][placeholder='https://…']");
  await newResultInput.fill("https://github.com/test-repo/pr-2");
  await page.getByRole("button", { name: "Отправить на проверку" }).click();
  await expect(page.getByRole("status").filter({ hasText: /проверке|review/i })).toBeVisible({ timeout: 10000 });

  // Проверим, что новый URL виден
  await expect(resultLink).toBeVisible();
  await expect(resultLink).toContainText("github.com/test-repo/pr-2");

  // 7. На проверке → Готово
  await page.getByRole("button", { name: "Принять результат" }).click();
  await expect(page.getByText("Результат принят")).toBeVisible({ timeout: 10000 });

  // 8. Проверяем через API, что result_url корректный
  const finalData = await bootstrap(page);
  const finalTask = finalData.tasks.find((t: any) => t.id === taskId);
  expect(finalTask.status).toBe("done");
  expect(finalTask.resultUrl).toBe("https://github.com/test-repo/pr-2");
  expect(finalTask.submittedAt).toBeTruthy();
  expect(finalTask.acceptedAt).toBeTruthy();

  // 9. Сброс и проверка очистки через API
  await api(page, `tasks/${taskId}/move`, { status: "todo" });
  const resetData = await bootstrap(page);
  const resetTask = resetData.tasks.find((t: any) => t.id === taskId);
  expect(resetTask.status).toBe("todo");
  expect(resetTask.resultUrl).toBe("");
  expect(resetTask.submittedAt).toBeNull();
  expect(resetTask.acceptedAt).toBeNull();
});

test("in_review → in_progress clears result_url", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1400 });
  await register(page);
  const pid = await createProject(page);
  const taskId = await seedTask(page, pid, "Задача с возвратом");
  await page.reload();

  await page.goto(`/projects/${pid}/tasks/${taskId}`);
  await expect(page.locator(".task-detail-page")).toBeVisible();

  // В работу → На проверку
  await page.getByRole("button", { name: "Начать работу" }).click();
  await expect(page.getByRole("status").filter({ hasText: /в работе|работе/i })).toBeVisible({ timeout: 10000 });

  await page.locator("input[type='url'][placeholder='https://…']").fill("https://figma.com/file-123");
  await page.getByRole("button", { name: "Отправить на проверку" }).click();
  await expect(page.getByRole("status").filter({ hasText: /проверке|review/i })).toBeVisible({ timeout: 10000 });

  // Вернуть в работу
  await page.getByRole("button", { name: "Вернуть на доработку" }).click();
  await page.getByLabel("Что нужно доработать?").fill("Поправить дизайн");
  await page.getByRole("button", { name: "Вернуть в работу", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // Перезагрузка
  await page.reload();

  // Проверяем через API
  const data = await bootstrap(page);
  const task = data.tasks.find((t: any) => t.id === taskId);
  expect(task.status).toBe("in_progress");
  expect(task.resultUrl).toBe("");
  expect(task.submittedAt).toBeNull();
});