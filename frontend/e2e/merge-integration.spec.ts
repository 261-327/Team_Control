import { expect, test } from "@playwright/test";
import { bootstrap, createProject, identity, register } from "./helpers";

test("colleagues, notification invitations and assistant coexist after merging main", async ({
  page,
  browser,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await register(page, identity("owner"));
  const projectId = await createProject(page, "Командный проект после объединения");
  const person = identity("colleague");
  const context = await browser.newContext();
  const colleague = await context.newPage();
  colleague.on("pageerror", (error) => errors.push(error.message));
  try {
    await register(colleague, person);
    await page.goto("/profile");
    await page.locator(".profile-colleague-add > summary").click();
    await page.getByLabel("Никнейм коллеги").fill(person.username);
    await page.getByRole("button", { name: "Отправить заявку", exact: true }).click();
    await expect(page.getByText("Заявка отправлена.", { exact: true })).toBeVisible();

    await colleague.getByRole("button", { name: /^Уведомления:/ }).click();
    const notifications = colleague.getByRole("dialog", { name: "Уведомления", exact: true });
    await notifications.getByRole("button", { name: "Принять", exact: true }).click();
    await expect(notifications.getByText("Коллега добавлен.", { exact: true })).toBeVisible();
    await colleague.keyboard.press("Escape");

    await page.reload();
    await page.getByLabel(`Действия с коллегой ${person.username}`, { exact: true }).click();
    await page.getByRole("button", { name: "Пригласить в проект", exact: true }).click();
    const invitation = page.getByRole("dialog", { name: "Пригласить в проект", exact: true });
    await invitation.getByLabel("Ваш проект", { exact: true }).selectOption(projectId);
    await invitation.getByRole("button", { name: "Пригласить", exact: true }).click();
    await expect(invitation).toHaveCount(0);
    expect((await bootstrap(colleague)).projects).toHaveLength(0);

    await colleague.reload();
    await colleague.getByRole("button", { name: /^Уведомления:/ }).click();
    await notifications.getByRole("button", { name: "Принять", exact: true }).click();
    const accept = colleague.getByRole("dialog", { name: "Принять приглашение", exact: true });
    await accept.getByRole("button", { name: "Принять и вступить", exact: true }).click();
    await expect(
      notifications.getByText("Вы присоединились к проекту.", { exact: true }),
    ).toBeVisible();
    const data = await bootstrap(colleague);
    expect(data.projects.map((project: { id: string }) => project.id)).toContain(projectId);
    await colleague.keyboard.press("Escape");
    await colleague.getByRole("button", { name: "Открыть ИИ-помощника", exact: true }).click();
    await expect(colleague.getByLabel("Сообщение помощнику")).toBeEnabled();
    expect(errors).toEqual([]);
  } finally {
    await context.close();
  }
});
