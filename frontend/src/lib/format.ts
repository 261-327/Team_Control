import type { Status, Task } from "@/types/domain";

export const statuses: Status[] = ["todo", "in_progress", "in_review", "done"];
export const statusLabels: Record<Status, string> = {
  todo: "К выполнению",
  in_progress: "В работе",
  in_review: "На проверке",
  done: "Готово",
};
export function statusIcon(status: Status) {
  return (
    (
      {
        todo: "circle",
        in_progress: "progress",
        in_review: "review",
        done: "checkCircle",
      } as Partial<Record<Status, string>>
    )[status] || "circle"
  );
}
export const professions = {
  developer: "Разработчик",
  designer: "Дизайнер",
  analyst: "Аналитик",
  security: "Специалист по безопасности",
  tester: "Тестировщик",
  other: "Другая роль",
};
export function initials(name: string) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((x) => x[0])
    .join("")
    .toUpperCase();
}
export function dateLabel(value: string, withTime = false) {
  if (!value) return "Без срока";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "short",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
    timeZone: "Europe/Moscow",
  }).format(new Date(value));
}
export function dayKey(value: string) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Moscow",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}
export function urgency(task: Task, now: string) {
  if (task.status === "done") return "done";
  const hours = (Date.parse(task.deadlineAt) - Date.parse(now)) / 3600000;
  return hours < 0 ? "overdue" : hours <= 24 ? "soon" : hours <= 48 ? "near" : "normal";
}
export function deadlineLabel(task: Task, now: string) {
  if (!task.deadlineAt) return "Без срока";
  if (task.status === "done") return dateLabel(task.deadlineAt);
  if (dayKey(task.deadlineAt) === dayKey(now)) return "Сегодня";
  if (dayKey(task.deadlineAt) === dayKey(new Date(Date.parse(now) + 86400000).toISOString()))
    return "Завтра";
  return dateLabel(task.deadlineAt);
}
export function toInputDate(value: string) {
  if (!value) return "";
  return new Date(Date.parse(value) + 3 * 3600000).toISOString().slice(0, 16);
}
export function fromInputDate(value: string) {
  return new Date(`${value}:00+03:00`).toISOString();
}
export function isWebUrl(value: string) {
  try {
    return ["http:", "https:"].includes(new URL(value).protocol);
  } catch {
    return false;
  }
}
export function plural(count: number, words = ["задача", "задачи", "задач"]) {
  const n = Math.abs(count) % 100;
  return `${count} ${words[n > 10 && n < 20 ? 2 : n % 10 === 1 ? 0 : n % 10 >= 2 && n % 10 <= 4 ? 1 : 2]}`;
}
