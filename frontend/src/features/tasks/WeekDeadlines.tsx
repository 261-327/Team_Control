"use client";
import Link from "next/link";
import { useState } from "react";
import { Button, IconButton } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import { useReadyData } from "@/providers/DataProvider";
import { calendarPeriod, shiftCalendar } from "@/lib/calendar-navigation";
import { dateLabel, dayKey } from "@/lib/format";
import type { Task } from "@/types/domain";
import { CalendarSwipe } from "./CalendarSwipe";

export function WeekDeadlines({ tasks }: { tasks: Task[] }) {
  const data = useReadyData();
  const today = dayKey(data.now);
  const [anchor, setAnchor] = useState(today);
  const { start, end } = calendarPeriod(anchor, "week");
  const first = dayKey(start.toISOString());
  const last = dayKey(end.toISOString());
  const upcoming = tasks
    .filter((task) => {
      const day = dayKey(task.deadlineAt);
      return day >= first && day <= last;
    })
    .sort((a, b) => Date.parse(a.deadlineAt) - Date.parse(b.deadlineAt));
  const navigate = (direction: number) =>
    setAnchor((value) => shiftCalendar(value, "week", direction));
  return (
    <section className="panel week-panel">
      <div className="panel-heading">
        <h2>Ближайшие сроки</h2>
        <Link href={`/calendar?day=${first}`} aria-label="Открыть календарь">
          <Icon name="upRight" size={17} />
        </Link>
      </div>
      <div className="mini-calendar-controls">
        <IconButton icon="back" label="Предыдущая неделя" onClick={() => navigate(-1)} />
        <p aria-live="polite">
          {new Intl.DateTimeFormat("ru-RU", {
            day: "numeric",
            month: "short",
            timeZone: "UTC",
          }).formatRange(start, end)}
        </p>
        <IconButton icon="arrow" label="Следующая неделя" onClick={() => navigate(1)} />
      </div>
      <CalendarSwipe className="calendar-swipe week-strip" onNavigate={navigate}>
        {Array.from({ length: 7 }, (_, index) => {
          const date = new Date(start.getTime() + index * 86400000);
          const day = dayKey(date.toISOString());
          return (
            <Link
              href={`/calendar?day=${day}`}
              key={day}
              className={day === today ? "current" : ""}
              aria-label={`Открыть ${dateLabel(date.toISOString())}`}
            >
              <span>{["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][index]}</span>
              <strong>{date.getUTCDate()}</strong>
              <i
                className={
                  upcoming.some((task) => dayKey(task.deadlineAt) === day) ? "has-tasks" : ""
                }
              />
            </Link>
          );
        })}
      </CalendarSwipe>
      <div className="mini-calendar-today">
        <Button variant="ghost" onClick={() => setAnchor(today)}>
          Текущая неделя
        </Button>
        <span>МСК</span>
      </div>
      <div className="upcoming-list">
        {upcoming.map((task) => (
          <Link key={task.id} href={`/projects/${task.projectId}/tasks/${task.id}`}>
            <span
              className={`upcoming-marker ${data.projects.find((project) => project.id === task.projectId)?.color}`}
            />
            <div>
              <strong>{task.title}</strong>
              <span>{dateLabel(task.deadlineAt, true)} МСК</span>
            </div>
          </Link>
        ))}
        {!upcoming.length && <p className="muted">На эту неделю дедлайнов нет.</p>}
      </div>
    </section>
  );
}
