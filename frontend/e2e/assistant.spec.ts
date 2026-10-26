import { expect, test } from "@playwright/test";
import { bootstrap, createProject, register, seedTask } from "./helpers";

test.describe("local AI with real models and Django", () => {
  test.skip(
    process.env.SIPI_TEST_AI !== "1",
    "Requires setup-ai.sh --images and both local workers",
  );
  test.setTimeout(180000);

  test("creates a project and tasks directly from chat, then adds more without duplicates", async ({
    page,
  }) => {
    await register(page);
    await page.getByRole("button", { name: "Открыть ИИ-помощника", exact: true }).click();
    const chat = page.getByRole("dialog", { name: "Сипи AI", exact: true });
    const message = chat.getByLabel("Сообщение помощнику");
    await expect(message).toBeEnabled();
    await message.fill(
      "Создай проект «Книгообмен» — сервис обмена книгами между студентами. Создай 3 задачи: каталог книг, поиск, заявки на обмен. Исполнителей и сроки не назначай.",
    );
    await chat.getByRole("button", { name: "Отправить сообщение", exact: true }).click();
    await expect(chat.getByText("Проект создан", { exact: true })).toBeVisible({ timeout: 90000 });
    const receipt = chat.locator(".assistant-receipt").first();
    await expect(receipt.locator("li")).toHaveCount(3);
    const before = await bootstrap(page);
    const project = before.projects.find((p: { name: string }) => p.name === "Книгообмен");
    expect(project).toBeTruthy();
    const tasks = before.tasks.filter((t: { projectId: string }) => t.projectId === project.id);
    expect(tasks).toHaveLength(3);
    expect(
      tasks.every(
        (t: { assigneeId: string; deadlineAt: string }) => !t.assigneeId && !t.deadlineAt,
      ),
    ).toBe(true);
    // A finished tool publishes the snapshot immediately, including the sidebar link.
    await expect(
      page.locator(".project-nav").getByRole("link", { name: "Книгообмен", exact: true }),
    ).toHaveCount(1);
    await message.fill("Добавь ещё 2 задачи: тестирование обмена и подготовка презентации.");
    await chat.getByRole("button", { name: "Отправить сообщение", exact: true }).click();
    await expect(chat.getByText("Задачи на доске", { exact: true })).toBeVisible({
      timeout: 90000,
    });
    const after = await bootstrap(page);
    expect(after.projects).toHaveLength(before.projects.length);
    expect(
      after.tasks.filter((t: { projectId: string }) => t.projectId === project.id),
    ).toHaveLength(5);
    await page.screenshot({ animations: "disabled", path: "/private/tmp/sipi-redesign-chat.png" });
    await page.reload();
    const final = await bootstrap(page);
    expect(final.tasks).toHaveLength(after.tasks.length);
    await page.goto(`/projects/${project.id}`);
    await expect(page.locator(".task-card")).toHaveCount(5);
    await page.screenshot({
      animations: "disabled",
      fullPage: true,
      path: "/private/tmp/sipi-redesign-board.png",
    });
    await page.goto("/my-tasks");
    await expect(page.getByRole("heading", { name: "Мои задачи", exact: true })).toBeVisible();
    await page.screenshot({
      animations: "disabled",
      fullPage: true,
      path: "/private/tmp/sipi-redesign-dashboard.png",
    });
    await page.setViewportSize({ width: 375, height: 812 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.screenshot({
      animations: "disabled",
      fullPage: true,
      path: "/private/tmp/sipi-redesign-mobile.png",
    });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  });

  test("answers cite real tasks; drafts require confirmation and persist across reload", async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await register(page);
    const pid = await createProject(page, "Запись в библиотеку");
    const existing = await seedTask(page, pid, "Проверить каталог библиотеки");
    const before = await bootstrap(page);
    await page.getByRole("button", { name: "Открыть ИИ-помощника", exact: true }).click();
    const chat = page.getByRole("dialog", { name: "Сипи AI", exact: true });
    await expect(chat.getByLabel("Сообщение помощнику")).toBeEnabled();
    await chat
      .getByLabel("Сообщение помощнику")
      .fill("Какие задачи уже есть в этом проекте? Приведи ссылки на задачи.");
    await chat.getByRole("button", { name: "Отправить сообщение", exact: true }).click();
    await expect(
      chat
        .locator(".assistant-sources")
        .getByRole("link", { name: "Проверить каталог библиотеки" }),
    ).toBeVisible({ timeout: 90000 });
    await expect(chat.locator(".assistant-sources a").last()).toHaveAttribute(
      "href",
      `/projects/${pid}/tasks/${existing}`,
    );
    await chat.getByRole("button", { name: "Черновик задач", exact: true }).click();
    await chat
      .getByLabel("Сообщение помощнику")
      .fill(
        "Создай план из трёх задач: наша команда делает приложение для поиска и бронирования книг. Каталог уже проверяем. Нужны поиск, бронирование, личный кабинет. Сроки и исполнителей пока не назначай.",
      );
    await chat.getByRole("button", { name: "Отправить сообщение", exact: true }).click();
    await expect(
      chat.getByRole("heading", { name: "Проверь задачи перед созданием", exact: true }),
    ).toBeVisible({ timeout: 90000 });
    expect((await bootstrap(page)).tasks).toHaveLength(before.tasks.length);
    const details = chat.locator(".assistant-draft");
    const count = await details.count();
    expect(count).toBe(3);
    await expect(chat.getByLabel("Описание задачи 1", { exact: true })).not.toHaveValue("");
    for (let index = 1; index < count; index++) {
      await details.nth(index).locator("summary").click();
      await details.nth(index).getByRole("checkbox").uncheck();
    }
    await chat
      .getByLabel("Название задачи 1", { exact: true })
      .fill("Подготовить поиск по библиотеке");
    await chat.getByLabel("Исполнитель задачи 1", { exact: true }).selectOption(before.sessionId);
    await page.screenshot({
      animations: "disabled",
      path: "/private/tmp/sipi-assistant-drafts-desktop.png",
    });
    await chat.getByRole("button", { name: "Создать выбранные задачи (1)", exact: true }).click();
    await expect(chat.getByText("Задачи созданы", { exact: true })).toBeVisible();
    const after = await bootstrap(page);
    expect(after.tasks).toHaveLength(before.tasks.length + 1);
    expect(
      after.tasks.filter((t: { title: string }) => t.title === "Подготовить поиск по библиотеке"),
    ).toHaveLength(1);
    await page.reload();
    await page.getByRole("button", { name: "Открыть ИИ-помощника", exact: true }).click();
    await expect(chat.getByText("Задачи созданы", { exact: true })).toBeVisible();
    await expect(
      chat
        .locator(".assistant-created-tasks")
        .getByRole("link", { name: "Подготовить поиск по библиотеке" }),
    ).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(chat).toHaveCSS("opacity", "1");
    await page.screenshot({
      animations: "disabled",
      path: "/private/tmp/sipi-assistant-mobile.png",
    });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.keyboard.press("Escape");
    await expect(chat).toHaveCount(0);
    expect(errors).toEqual([]);
  });

  test("local image generation returns a protected downloadable PNG", async ({ page }) => {
    await register(page);
    await createProject(page, "Библиотека Политеха — логотип");
    await page.getByRole("button", { name: "Открыть ИИ-помощника", exact: true }).click();
    const chat = page.getByRole("dialog", { name: "Сипи AI", exact: true });
    await expect(chat.getByLabel("Сообщение помощнику")).toBeEnabled();
    await chat.getByRole("button", { name: "Логотип", exact: true }).click();
    await chat
      .getByLabel("Сообщение помощнику")
      .fill(
        "Нарисуй один простой логотип: раскрытая книга и маленькое солнце, жёлтый и графитовый цвета, белый фон. Без букв и надписей.",
      );
    await chat.getByRole("button", { name: "Отправить сообщение", exact: true }).click();
    const image = chat.getByAltText("Концепт логотипа по описанию проекта");
    await expect(image).toBeVisible({ timeout: 120000 });
    const src = (await image.getAttribute("src"))!;
    const response = await page.request.get(src);
    expect(response.headers()["content-type"]).toContain("image/png");
    expect(
      (await response.body()).subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])),
    ).toBe(true);
    await expect(chat.getByRole("link", { name: "Скачать PNG", exact: true })).toHaveAttribute(
      "href",
      src,
    );
    await page.screenshot({
      animations: "disabled",
      path: "/private/tmp/sipi-assistant-image-browser.png",
    });
    await page.reload();
    await page.getByRole("button", { name: "Открыть ИИ-помощника", exact: true }).click();
    await expect(chat.getByAltText("Концепт логотипа по описанию проекта")).toBeVisible();
    await chat.getByRole("button", { name: "Очистить историю помощника", exact: true }).click();
    await page
      .getByRole("dialog", { name: "Очистить переписку?", exact: true })
      .getByRole("button", { name: "Очистить", exact: true })
      .click();
    await expect(chat.getByRole("heading", { name: "С чего начнём?", exact: true })).toBeVisible();
    expect((await page.request.get(src)).status()).toBe(404);
  });
});
