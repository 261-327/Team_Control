import { expect, test } from "@playwright/test";
import {
  bootstrap,
  createProject,
  identity,
  mailCode,
  password,
  register,
  seedTask,
} from "./helpers";

test("real registration, invitation, full task workflow and database persistence", async ({
  page,
  browser,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await register(page, identity("owner"));
  const projectId = await createProject(page);
  const memberIdentity = identity("member");
  await page.getByRole("link", { name: /Команда/ }).click();
  await page.getByRole("button", { name: "Пригласить участника", exact: true }).click();
  await page.getByLabel("Почта участника").fill(memberIdentity.email);
  await page.getByRole("button", { name: "Создать приглашение", exact: true }).click();
  const invitationUrl = await page.getByLabel("Ссылка на приглашение").inputValue();
  const memberContext = await browser.newContext();
  const member = await memberContext.newPage();
  await register(member, memberIdentity);
  await member.goto(invitationUrl);
  await member.getByRole("button", { name: "Принять приглашение", exact: true }).click();
  await expect(member).toHaveURL(new RegExp(`/projects/${projectId}$`));
  const memberId = (await bootstrap(member)).sessionId;
  await page.goto(`/projects/${projectId}`);
  await page.getByRole("button", { name: "Новая задача", exact: true }).click();
  const form = page.getByRole("dialog", { name: "Новая задача", exact: true });
  await form.getByLabel("Название задачи").fill("Проверить связку с Django");
  await form.getByLabel("Исполнитель").selectOption(memberId);
  await form.getByRole("button", { name: "Создать задачу", exact: true }).click();
  await expect(form).toHaveCount(0);
  const task = (await bootstrap(page)).tasks.find(
    (t: { title: string }) => t.title === "Проверить связку с Django",
  );
  const taskUrl = `/projects/${projectId}/tasks/${task.id}`;
  await member.goto(taskUrl);
  await member.getByRole("button", { name: "Начать работу", exact: true }).click();
  await member.getByLabel("Ссылка на результат").fill("https://example.com/result");
  await member.getByRole("button", { name: "Отправить на проверку", exact: true }).click();
  await expect(
    member.getByRole("heading", { name: "Результат на проверке", exact: true }),
  ).toBeVisible();
  await member.getByLabel("Твой комментарий").fill("Готово, можно проверять.");
  await member.getByRole("button", { name: "Отправить", exact: true }).click();
  await expect(member.getByText("Готово, можно проверять.", { exact: true })).toBeVisible();
  await page.goto(taskUrl);
  await page.getByRole("button", { name: "Вернуть на доработку", exact: true }).click();
  await page.getByLabel("Что нужно доработать?").fill("Уточнить требования.");
  await page.getByRole("button", { name: "Вернуть в работу", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await member.reload();
  await member.getByRole("button", { name: "Отправить на проверку", exact: true }).click();
  await expect(
    member.getByRole("heading", { name: "Результат на проверке", exact: true }),
  ).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Принять результат", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Результат принят", exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Результат принят", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /История/ }).click();
  await expect(page.getByText(/Уточнить требования\./)).toBeVisible();
  expect(errors).toEqual([]);
  await memberContext.close();
});

test("real OTP rejects wrong codes, resumes after reload, and logout clears private data", async ({
  page,
}) => {
  const person = await register(page);
  await page.goto("/profile");
  await page.getByRole("button", { name: "Выйти из аккаунта", exact: true }).click();
  await expect(page).toHaveURL(/login/);
  await page.getByLabel("Логин или почта").fill(person.username);
  await page.getByLabel("Пароль", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Продолжить", exact: true }).click();
  await expect(page.getByLabel("Шестизначный код")).toBeVisible();
  const code = await mailCode(person.email);
  await page.getByLabel("Шестизначный код").fill(code === "000000" ? "111111" : "000000");
  await page.getByRole("button", { name: "Подтвердить и войти", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Неверный код" })).toBeVisible();
  await page.reload();
  await page.getByLabel("Шестизначный код").fill(code);
  await page.getByRole("button", { name: "Подтвердить и войти", exact: true }).click();
  await expect(page).toHaveURL(/my-tasks$/);
  await page.goto("/profile");
  await page.getByRole("button", { name: "Выйти из аккаунта", exact: true }).click();
  await page.goto("/projects");
  await expect(page).toHaveURL(/login/);
  expect((await bootstrap(page)).projects).toEqual([]);
});

test("server errors preserve drafts; assistant opens scoped conversation; no demo accounts remain", async ({
  page,
}) => {
  await register(page);
  const pid = await createProject(page);
  const id = (await bootstrap(page)).sessionId;
  await page.getByRole("button", { name: "Новая задача", exact: true }).click();
  const form = page.getByRole("dialog", { name: "Новая задача", exact: true });
  await form.getByLabel("Название задачи").fill("Сохранить черновик при ошибке");
  await form.getByLabel("Исполнитель").selectOption(id);
  await page.route("**/api/tasks", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: { message: "Сервер временно недоступен" } }),
    }),
  );
  await form.getByRole("button", { name: "Создать задачу", exact: true }).click();
  await expect(form.getByRole("alert")).toContainText("Сервер временно недоступен");
  await expect(form.getByLabel("Название задачи")).toHaveValue("Сохранить черновик при ошибке");
  await page.unroute("**/api/tasks");
  await form.getByRole("button", { name: "Создать задачу", exact: true }).click();
  await expect(form).toHaveCount(0);
  await page.getByRole("button", { name: "Открыть ИИ-помощника", exact: true }).click();
  await expect(page.getByRole("heading", { name: "С чего начнём?", exact: true })).toBeVisible();
  await expect(page.getByLabel("Контекст", { exact: true })).toHaveValue(pid);
  await expect(page.getByRole("button", { name: "Черновик задач", exact: true })).toBeVisible();
  expect(
    (await bootstrap(page)).tasks.filter((t: { projectId: string }) => t.projectId === pid),
  ).toHaveLength(1);
  await expect(page.getByText("Демо", { exact: true })).toHaveCount(0);
});

for (const width of [390, 768, 1440]) {
  test(`real screens fit ${width}px and dialogs support keyboard`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await register(page);
    const pid = await createProject(page);
    const tid = await seedTask(page, pid, "Проверить адаптивность");
    for (const route of [
      "/my-tasks",
      "/projects",
      `/projects/${pid}`,
      `/projects/${pid}/members`,
      `/projects/${pid}/materials`,
      `/projects/${pid}/settings`,
      `/projects/${pid}/tasks/${tid}`,
      "/calendar",
      "/overview",
      "/profile",
      "/projects/search",
      "/projects/new",
    ]) {
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      ).toBe(true);
    }
    await page.goto(`/projects/${pid}`);
    await page.getByRole("button", { name: "Новая задача", exact: true }).click();
    await expect(page.getByLabel("Название задачи")).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.getByRole("button", { name: "Открыть ИИ-помощника", exact: true }).click();
    await expect(page.getByLabel("Сообщение помощнику")).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });
}

test("a delayed save response cannot restore private data after logout", async ({ page }) => {
  await register(page);
  await createProject(page);
  await page.goto("/profile");
  let release!: () => void;
  let committed!: () => void;
  const saved = new Promise<void>((resolve) => {
    committed = resolve;
  });
  const delay = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/profile", async (route) => {
    const response = await route.fetch();
    committed();
    await delay;
    await route.fulfill({ response });
  });
  await page.getByLabel("Имя и фамилия").fill("Обновлённое имя");
  await page.getByRole("button", { name: "Сохранить изменения", exact: true }).click();
  await saved;
  await page.getByRole("button", { name: "Выйти из аккаунта", exact: true }).click();
  await expect(page).toHaveURL(/login/);
  const response = page.waitForResponse((r) => r.url().endsWith("/api/profile"));
  release();
  await (await response).finished();
  await page.getByLabel("Логин или почта").fill("Проверка завершения ответа");
  await expect(page).toHaveURL(/login/);
  await expect(page.getByRole("heading", { name: "Вход в Сипи", exact: true })).toBeVisible();
});
