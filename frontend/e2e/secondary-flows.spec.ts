import { expect, test } from "@playwright/test";
import { register, createProject } from "./helpers";

test("project creation, column settings, materials, profile and safe cancellation persist together", async ({
  page,
}) => {
  await register(page);
  await createProject(page);
  await page.getByRole("button", { name: "Новая задача", exact: true }).click();
  await page.getByLabel("Название задачи").fill("Черновик, который не должен сохраниться");
  await page.keyboard.press("Escape");
  const discard = page.getByRole("dialog", { name: "Закрыть без сохранения?" });
  await expect(discard).toBeVisible();
  await discard.getByRole("button", { name: "Отмена", exact: true }).click();
  await expect(page.getByLabel("Название задачи")).toHaveValue(
    "Черновик, который не должен сохраниться",
  );
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Не сохранять", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(await page.evaluate(() => document.body.style.overflow)).not.toBe("hidden");
  await expect(
    page.getByRole("link", { name: /Черновик, который не должен сохраниться/ }),
  ).toHaveCount(0);

  await page.goto("/projects/new");
  await page.getByLabel("Название проекта").fill("Учебный проект для проверки интерфейса");
  await page.getByLabel("Описание").fill("Проверяем работу связанного пространства.");
  await page.getByRole("button", { name: "Создать проект", exact: true }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Учебный проект для проверки интерфейса" }),
  ).toBeVisible();
  const projectUrl = page.url();
  await page.getByRole("link", { name: "Настройки", exact: true }).click();
  await page.getByRole("button", { name: "Изменить колонку «К выполнению»", exact: true }).click();
  const column = page.getByRole("dialog", { name: "Настройки колонки" });
  await column.getByLabel("Название", { exact: false }).fill("Запланировано");
  await column.getByLabel("Лимит задач").fill("7");
  await column.getByRole("button", { name: "Сохранить", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("link", { name: /Материалы/ }).click();
  await page.getByRole("button", { name: "Добавить материал", exact: true }).click();
  const material = page.getByRole("dialog", { name: "Новый материал" });
  await material.getByLabel("Название", { exact: false }).fill("Требования к защите");
  await material.getByLabel("Ссылка", { exact: false }).fill("https://example.com/requirements");
  await material.getByRole("button", { name: "Добавить материал", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Требования к защите", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: /example.com/ })).toHaveAttribute(
    "href",
    "https://example.com/requirements",
  );
  await page.goto(projectUrl);
  await page.getByRole("button", { name: "Доска", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Запланировано", exact: true })).toBeVisible();
  await expect(page.getByText("0 / 7", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Черновик, который не должен сохраниться/ }),
  ).toHaveCount(0);
  await page.goto("/profile");
  await page.getByLabel("Имя и фамилия").fill("Александр Проверкин");
  await page.getByRole("button", { name: "Сохранить изменения", exact: true }).click();
  await expect(page.locator(".profile-summary h2")).toHaveText("Александр Проверкин");
  await page.reload();
  await expect(page.getByLabel("Имя и фамилия")).toHaveValue("Александр Проверкин");
});
