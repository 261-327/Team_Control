"use client";

import Link from "next/link";
import { useState } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { useUi } from "@/providers/UiContext";
import { Button, EmptyState, IconButton } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import { dayKey, dateLabel } from "@/lib/format";
import { createCalendar } from "@/lib/calendar";
import { TaskList } from "./TaskViews";

export function CalendarView() {
  const data = useReadyData();
  const ui = useUi();
  const now = new Date(data.now);
  const [offset, setOffset] = useState(0);
  const [selectedDay, setSelectedDay] = useState("");
  const [projectId, setProjectId] = useState("");
  const month = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + offset, 1));
  const start = new Date(month);
  start.setUTCDate(1 - ((month.getUTCDay() + 6) % 7));
  const end = new Date(Date.UTC(month.getUTCFullYear(), month.getUTCMonth() + 1, 0));
  const cells = Math.ceil((((month.getUTCDay() + 6) % 7) + end.getUTCDate()) / 7) * 7;
  const mine = data.tasks.filter((t) => t.assigneeId === data.sessionId && t.status !== "done");
  const visible = mine.filter((t) => !projectId || t.projectId === projectId);
  const week = mine.filter(
    (t) =>
      Date.parse(t.deadlineAt) >= Date.parse(data.now) &&
      Date.parse(t.deadlineAt) < Date.parse(data.now) + 7 * 86400000,
  );
  const dayTasks = visible
    .filter((t) => !selectedDay || dayKey(t.deadlineAt) === selectedDay)
    .sort((a, b) => Date.parse(a.deadlineAt) - Date.parse(b.deadlineAt));
  const exportCalendar = () => {
    if (!week.length) {
      ui.notify("На ближайшие 7 дней нет личных дедлайнов");
      return;
    }
    const blob = new Blob([createCalendar(week, data.projects, data.now)], {
      type: "text/calendar;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sipi-deadlines.ics";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    ui.notify("Дедлайны на ближайшие 7 дней выгружены");
  };
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>
            Календарь<span className="heading-dot">.</span>
          </h1>
          <p>Твои личные дедлайны из всех проектов. Время — московское.</p>
        </div>
        <Button variant="secondary" onClick={exportCalendar} disabled={!week.length}>
          <Icon name="download" size={17} />
          Экспорт на 7 дней
        </Button>
      </div>
      <section className="panel calendar-panel">
        <div className="calendar-toolbar">
          <div>
            <h2>
              {new Intl.DateTimeFormat("ru-RU", {
                month: "long",
                year: "numeric",
                timeZone: "UTC",
              }).format(month)}
            </h2>
            <span>МСК · UTC+3</span>
          </div>
          <label className="sr-only" htmlFor="calendar-project">
            Проект
          </label>
          <select
            id="calendar-project"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            <option value="">Все мои проекты</option>
            {data.projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <div className="button-wrap">
            <Button
              variant="ghost"
              onClick={() => {
                setOffset(0);
                setSelectedDay(dayKey(data.now));
              }}
            >
              Сегодня
            </Button>
            <IconButton
              icon="back"
              label="Предыдущий месяц"
              onClick={() => setOffset(offset - 1)}
            />
            <IconButton
              icon="arrow"
              label="Следующий месяц"
              onClick={() => setOffset(offset + 1)}
            />
          </div>
        </div>
        <div className="calendar-weekdays">
          {["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"].map(
            (d) => (
              <span key={d}>
                {d}
                <abbr>{d.slice(0, 2)}</abbr>
              </span>
            ),
          )}
        </div>
        <div className="calendar-grid">
          {Array.from({ length: cells }, (_, i) => {
            const date = new Date(Date.parse(start.toISOString()) + i * 86400000);
            const iso = date.toISOString();
            const key = dayKey(iso);
            const tasks = visible.filter((t) => dayKey(t.deadlineAt) === key);
            return (
              <div
                className={`calendar-cell ${date.getUTCMonth() !== month.getUTCMonth() ? "outside" : ""} ${key === dayKey(data.now) ? "today" : ""} ${selectedDay === key ? "selected" : ""}`}
                key={key}
              >
                <button
                  className="calendar-day-button"
                  onClick={() => setSelectedDay(selectedDay === key ? "" : key)}
                  aria-label={`${dateLabel(iso)}, ${tasks.length} задач`}
                  aria-pressed={selectedDay === key}
                >
                  {date.getUTCDate()}
                  <span className="calendar-mobile-count">{tasks.length || ""}</span>
                </button>
                <div className="calendar-cell-tasks">
                  {tasks.slice(0, 2).map((t) => (
                    <Link
                      key={t.id}
                      href={`/projects/${t.projectId}/tasks/${t.id}`}
                      className={data.projects.find((p) => p.id === t.projectId)?.color}
                    >
                      <span /> {t.title}
                    </Link>
                  ))}
                  {tasks.length > 2 && (
                    <button onClick={() => setSelectedDay(key)}>Ещё {tasks.length - 2}</button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>
      <section className="panel calendar-task-panel">
        <div className="panel-heading">
          <h2>
            {selectedDay
              ? `Задачи на ${dateLabel(`${selectedDay}T12:00:00+03:00`)}`
              : "Все предстоящие задачи"}
          </h2>
          {selectedDay && (
            <Button variant="ghost" onClick={() => setSelectedDay("")}>
              Показать все
            </Button>
          )}
        </div>
        {dayTasks.length ? (
          <TaskList tasks={dayTasks} />
        ) : (
          <EmptyState
            icon="calendar"
            title="На эту дату задач нет"
            description="На выбранную дату задач нет."
          />
        )}
      </section>
      <p className="calendar-export-note">
        <Icon name="download" size={14} />
        Экспорт включает только твои незавершённые задачи на ближайшие 7 дней. Это файл .ics для
        разового импорта; дальнейшие изменения автоматически не обновляются.
      </p>
    </>
  );
}
