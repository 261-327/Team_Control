export type CalendarMode = "week" | "month";

// Calendar dates are Moscow day keys, represented at UTC noon for date arithmetic.
export function calendarPeriod(anchor: string, mode: CalendarMode) {
  const month = new Date(`${anchor}T12:00:00Z`);
  month.setUTCDate(1);
  const start = new Date(mode === "week" ? `${anchor}T12:00:00Z` : month);
  start.setUTCDate(start.getUTCDate() - ((start.getUTCDay() + 6) % 7));
  const last = new Date(Date.UTC(month.getUTCFullYear(), month.getUTCMonth() + 1, 0, 12));
  const cells =
    mode === "week" ? 7 : Math.ceil((((month.getUTCDay() + 6) % 7) + last.getUTCDate()) / 7) * 7;
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + cells - 1);
  return { start, end, month, cells };
}

export function shiftCalendar(anchor: string, mode: CalendarMode, direction: number) {
  const date = new Date(`${anchor}T12:00:00Z`);
  if (mode === "week") date.setUTCDate(date.getUTCDate() + direction * 7);
  else {
    // Start at day 1 so January 31 never skips February.
    date.setUTCDate(1);
    date.setUTCMonth(date.getUTCMonth() + direction);
  }
  return date.toISOString().slice(0, 10);
}

export function calendarSwipe(dx: number, dy: number, elapsed: number): -1 | 0 | 1 {
  if (elapsed < 0 || elapsed > 1000 || Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy) * 1.5)
    return 0;
  return dx < 0 ? 1 : -1;
}
