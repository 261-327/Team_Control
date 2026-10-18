import { expect, test } from "@playwright/test";
import { createDatabase } from "./fixtures";
import { allowedTransitions, canAccess, canManage } from "../src/lib/permissions";
import { urgency, dayKey } from "../src/lib/format";
import { createCalendar } from "../src/lib/calendar";

test("project roles, teaching scope and exact deadline boundaries share one policy", () => {
  const db = createDatabase();
  db.sessionId = "alex";
  expect(canManage(db, "sipi")).toBe(true);
  expect(canManage(db, "campus")).toBe(false);
  expect(canAccess(db, "robotics")).toBe(false);
  const task = { ...db.tasks[0], assigneeId: "alex", status: "todo" as const };
  expect(allowedTransitions(db, task)).toEqual(["in_progress"]);
  expect(allowedTransitions(db, { ...task, status: "in_review" })).toEqual(["done", "in_progress"]);
  db.sessionId = "elena";
  expect(canAccess(db, "sipi")).toBe(true);
  expect(canAccess(db, "robotics")).toBe(false);
  expect(allowedTransitions(db, { ...task, status: "in_review" })).toEqual([]);
  db.sessionId = "staff";
  expect(canManage(db, "campus")).toBe(true);
  expect(canAccess(db, "robotics")).toBe(false);
  for (const [hours, expected] of [
    [-0.001, "overdue"],
    [0, "soon"],
    [24, "soon"],
    [24.001, "near"],
    [48, "near"],
    [48.001, "normal"],
  ] as const) {
    expect(
      urgency(
        { ...task, deadlineAt: new Date(Date.parse(db.now) + hours * 3600000).toISOString() },
        db.now,
      ),
    ).toBe(expected);
  }
  expect(urgency({ ...task, status: "done", deadlineAt: "2020-01-01T00:00:00Z" }, db.now)).toBe(
    "done",
  );
  expect(dayKey("2026-10-18T22:00:00Z")).toBe("2026-10-19");
});

test("calendar preserves Unicode, Moscow deadline instants, escaping and RFC line folding", () => {
  const db = createDatabase();
  const task = {
    ...db.tasks[0],
    title: "Проверка; перенос, обратный слеш \\ и длинное название ".repeat(4) + "\nНовая строка",
    deadlineAt: "2026-10-18T18:00:00+03:00",
  };
  const calendar = createCalendar([task], db.projects, db.now);
  expect(calendar.endsWith("\r\n")).toBe(true);
  for (const line of calendar.split("\r\n"))
    expect(Buffer.byteLength(line, "utf8")).toBeLessThanOrEqual(75);
  const unfolded = calendar.replace(/\r\n[ \t]/g, "");
  expect(unfolded).toContain("DTSTART:20261018T150000Z\r\n");
  expect(unfolded).toContain(`UID:sipi-${task.id}@sipi.local`);
  expect(unfolded).toContain("Проверка\\; перенос\\, обратный слеш \\\\");
  expect(unfolded).toContain("\\nНовая строка");
  expect(unfolded.match(/BEGIN:VEVENT/g)).toHaveLength(1);
  expect(unfolded.match(/END:VEVENT/g)).toHaveLength(1);
  expect(unfolded).not.toContain("example.com");
});
