// Build-time public metadata stays tied to the bundle open in this browser.
const revision = process.env.NEXT_PUBLIC_SIPI_REVISION || "";

export const release = {
  version: process.env.NEXT_PUBLIC_SIPI_VERSION || "dev",
  revision,
  shortRevision: revision.slice(0, 7),
  builtAt: process.env.NEXT_PUBLIC_SIPI_BUILT_AT || "",
  environment:
    process.env.NEXT_PUBLIC_SIPI_ENVIRONMENT === "production"
      ? "Рабочий сайт"
      : process.env.NEXT_PUBLIC_SIPI_ENVIRONMENT === "preview"
        ? "Тестовая сборка"
        : "Локальная сборка",
  commitUrl: revision ? `https://github.com/261-327/Team_Control/commit/${revision}` : "",
  // Update release notes alongside the package version. The build revision is automatic.
  changes: [
    "Файлы в материалах проекта, задачах и чате ИИ.",
    "Создание своих этапов на доске и обновлённая проверка доступа.",
    "Переход к списку просроченных задач по кнопке «Посмотреть».",
  ],
};
