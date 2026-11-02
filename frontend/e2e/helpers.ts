import { expect, type Page } from "@playwright/test";
import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";

// Mail is read only from the isolated test server's file backend, never from an API.
const mailPath = process.env.SIPI_TEST_MAIL_DIR;
export const password = "Browser-test-628!";
export function identity(label = "student") {
  const username = `${label}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  return {
    username,
    email: `${username}@example.com`,
    name: label === "owner" ? "Руководитель проекта" : "Участник проекта",
  };
}
export async function mailCode(email: string) {
  if (!mailPath)
    throw new Error("Set SIPI_TEST_MAIL_DIR to the isolated Django file-mail directory.");
  let code = "";
  await expect
    .poll(async () => {
      const files = await Promise.all(
        (await readdir(mailPath)).map(async (name) => ({
          name,
          modified: (await stat(path.join(mailPath, name))).mtimeMs,
        })),
      );
      for (const file of files.sort((a, b) => b.modified - a.modified)) {
        const contents = await readFile(path.join(mailPath, file.name), "utf8");
        // Django can append multiple messages to the same file within one second.
        for (const message of contents.split(/\r?\n-{20,}\r?\n/).reverse()) {
          if (!message.includes(`To: ${email}`)) continue;
          const body = message.includes("Content-Transfer-Encoding: base64")
            ? Buffer.from(message.split(/\r?\n\r?\n/)[1].trim(), "base64").toString("utf8")
            : message;
          const match = body.match(/Ваш код: (\d{6})/);
          if (match) {
            code = match[1];
            return code;
          }
        }
      }
      return "";
    })
    .toMatch(/^\d{6}$/);
  return code;
}
export async function register(page: Page, person = identity()) {
  await page.goto("/register");
  await page.getByLabel("Имя и фамилия").fill(person.name);
  await page.getByLabel("Логин", { exact: true }).fill(person.username);
  await page.getByLabel("Электронная почта").fill(person.email);
  await page.getByLabel("Пароль", { exact: true }).fill(password);
  await page.getByLabel("Повтори пароль").fill(password);
  await page.getByRole("button", { name: "Создать аккаунт", exact: true }).click();
  await expect(page.getByLabel("Шестизначный код")).toBeVisible();
  await page.getByLabel("Шестизначный код").fill(await mailCode(person.email));
  await page.getByRole("button", { name: "Подтвердить и войти", exact: true }).click();
  await expect(page).toHaveURL(/my-tasks$/);
  return person;
}
export async function createProject(page: Page, name = `Проект ${Date.now()}`) {
  await page.goto("/projects/new");
  await page.getByLabel("Название проекта").fill(name);
  await page.getByLabel("Описание", { exact: false }).fill("Проект для проверки связи с Django.");
  await page.getByRole("button", { name: "Создать проект", exact: true }).click();
  await expect(page).toHaveURL(/\/projects\/\d+$/);
  const projectId = page.url().split("/").pop()!;
  return projectId;
}
export async function bootstrap(page: Page) {
  const response = await page.request.get("/api/bootstrap");
  expect(response.ok()).toBe(true);
  return response.json();
}
export async function api(page: Page, route: string, data?: unknown, method = "POST") {
  const csrf = (await page.context().cookies()).find((c) => c.name === "csrftoken")!.value;
  return page.request.fetch(`/api/${route}`, {
    method,
    data,
    headers: { "X-CSRFToken": csrf, "Content-Type": "application/json" },
  });
}
export async function seedTask(page: Page, projectId: string, title: string) {
  const data = await bootstrap(page);
  const response = await api(page, "tasks", {
    projectId,
    title,
    description: "",
    assigneeId: data.sessionId,
    deadlineAt: new Date(Date.now() + 86400000).toISOString(),
    tag: "Команда",
  });
  expect(response.ok()).toBe(true);
  return (await response.json()).task.id as string;
}

export async function mailPasswordResetLink(email: string) {
  if (!mailPath) throw new Error("Set SIPI_TEST_MAIL_DIR to the isolated Django file-mail directory.");
  let link = "";
  await expect.poll(async () => {
    const files = await Promise.all((await readdir(mailPath)).map(async (name) => ({
      name, modified: (await stat(path.join(mailPath, name))).mtimeMs,
    })));
    for (const file of files.sort((a, b) => b.modified - a.modified)) {
      const contents = await readFile(path.join(mailPath, file.name), "utf8");
      for (const message of contents.split("--------------------").reverse()) {
        if (!message.includes("To: " + email) || !message.includes("Восстановление пароля")) continue;
        const body = message.includes("Content-Transfer-Encoding: base64")
          ? Buffer.from(message.split("\n\n").pop()!.trim(), "base64").toString("utf8") : message;
        const line = body.split("\n").find((item) => item.includes("reset-password?uid="));
        if (line) { const start = line.indexOf("http"); if (start >= 0) { link = line.slice(start).trim().split(" ")[0]; return link; } }
      }
    }
    return "";
  }).toContain("reset-password?uid=");
  return link;
}
