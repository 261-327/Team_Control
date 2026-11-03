import { expect, test } from "@playwright/test";
import { calendarPeriod, calendarSwipe, shiftCalendar } from "../src/lib/calendar-navigation";
import { dayKey } from "../src/lib/format";

test("weeks start on Monday and cross month/year boundaries", () => {
  const { start, end, cells } = calendarPeriod("2027-01-01", "week");
  expect(dayKey(start.toISOString())).toBe("2026-12-28");
  expect(dayKey(end.toISOString())).toBe("2027-01-03");
  expect(cells).toBe(7);
  expect(shiftCalendar("2026-12-28", "week", 1)).toBe("2027-01-04");
  expect(shiftCalendar("2027-01-04", "week", -1)).toBe("2026-12-28");
});

test("Moscow midnight selects the correct week", () => {
  const today = dayKey("2026-11-01T22:00:00Z");
  expect(today).toBe("2026-11-02");
  expect(dayKey(calendarPeriod(today, "week").start.toISOString())).toBe("2026-11-02");
});

test("month navigation does not skip February, including leap years", () => {
  expect(shiftCalendar("2028-01-31", "month", 1)).toBe("2028-02-01");
  const period = calendarPeriod("2028-02-29", "month");
  expect(period.cells).toBe(35);
  expect(dayKey(period.start.toISOString())).toBe("2028-01-31");
  expect(dayKey(period.end.toISOString())).toBe("2028-03-05");
  expect(calendarPeriod("2026-03-01", "month").cells).toBe(42);
});

test("swipes navigate in both directions and ignore taps, scrolling and long presses", () => {
  expect(calendarSwipe(-100, 10, 250)).toBe(1);
  expect(calendarSwipe(100, -10, 250)).toBe(-1);
  expect(calendarSwipe(10, 2, 100)).toBe(0);
  expect(calendarSwipe(-70, 100, 250)).toBe(0);
  expect(calendarSwipe(-80, 70, 250)).toBe(0);
  expect(calendarSwipe(-100, 0, 1500)).toBe(0);
});
