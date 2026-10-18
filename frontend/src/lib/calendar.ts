import type { Project, Task } from "@/types/domain";

function escapeText(text: string) {
  return text
    .replace(/\\/g, "\\\\")
    .replace(/\r?\n/g, "\\n")
    .replace(/;/g, "\\;")
    .replace(/,/g, "\\,");
}
function utcDate(value: string) {
  return new Date(value)
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\.\d{3}Z$/, "Z");
}
/** RFC 5545: fold at 75 octets without splitting a UTF-8 character. */
function fold(line: string) {
  let result = "";
  let bytes = 0;
  for (const char of line) {
    const size = new TextEncoder().encode(char).length;
    if (bytes + size > 75) {
      result += "\r\n ";
      bytes = 1;
    }
    result += char;
    bytes += size;
  }
  return result;
}
export function createCalendar(tasks: Task[], projects: Project[], now: string) {
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Sipi//Student deadlines//RU",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Сипи — мои дедлайны",
  ];
  for (const task of tasks.filter((task) => task.deadlineAt))
    lines.push(
      "BEGIN:VEVENT",
      `UID:sipi-${task.id}@sipi.local`,
      `DTSTAMP:${utcDate(now)}`,
      `DTSTART:${utcDate(task.deadlineAt)}`,
      `SUMMARY:${escapeText(task.title)}`,
      `DESCRIPTION:${escapeText(`Срок задачи. Проект: ${projects.find((p) => p.id === task.projectId)?.name || "Проект"}. Экспорт из Сипи.`)}`,
      "END:VEVENT",
    );
  lines.push("END:VCALENDAR");
  return lines.map(fold).join("\r\n") + "\r\n";
}
