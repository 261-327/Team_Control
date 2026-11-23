"use client";
import { isAssigned } from "@/lib/permissions";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { useUi } from "@/providers/UiContext";
import { Button, EmptyState, IconButton } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import { dayKey, dateLabel, plural, statusLabels, urgency } from "@/lib/format";
import type { Status } from "@/types/domain";
import { createCalendar } from "@/lib/calendar";
import { calendarPeriod, shiftCalendar, type CalendarMode } from "@/lib/calendar-navigation";
import { TaskList } from "./TaskViews";
import { CalendarSwipe } from "./CalendarSwipe";
import { useSearchParams } from "next/navigation";

export function CalendarView() {
  const data = useReadyData();
  const ui = useUi();
  const today = dayKey(data.now);
  const searchParams = useSearchParams();
  const requested = searchParams.get("day") || "";
  const validDay =
    /^\d{4}-\d{2}-\d{2}$/.test(requested) &&
    Number.isFinite(Date.parse(`${requested}T12:00:00Z`)) &&
    new Date(`${requested}T12:00:00Z`).toISOString().slice(0, 10) === requested;
  const [anchor, setAnchor] = useState(validDay ? requested : today);
  const [mode, setMode] = useState<CalendarMode>("week");
  const [selectedDay, setSelectedDay] = useState(validDay ? requested : "");
  const [projectId, setProjectId] = useState("");
  const [status, setStatus] = useState<Status | "">("");
  const [deadlineFilter, setDeadlineFilter] = useState<"" | "overdue" | "today" | "upcoming">("");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const { start, end, month, cells: periodCells } = calendarPeriod(anchor, mode);
  const cells = mode === "week" && deadlineFilter === "upcoming" ? 14 : periodCells;
  const firstKey = start.toISOString().slice(0, 10);
  const gridEnd = new Date(start);
  gridEnd.setUTCDate(gridEnd.getUTCDate() + cells - 1);
  const lastKey = gridEnd.toISOString().slice(0, 10);
  const upcomingEnd = new Date(`${today}T12:00:00Z`);
  upcomingEnd.setUTCDate(upcomingEnd.getUTCDate() + 6);
  const upcomingLastKey = upcomingEnd.toISOString().slice(0, 10);
  const navigate = (direction: number) => {
    setAnchor((value) => shiftCalendar(value, mode, direction));
    setSelectedDay("");
    if (deadlineFilter === "upcoming") setDeadlineFilter("");
  };
  const periodLabel =
    mode === "week"
      ? new Intl.DateTimeFormat("ru-RU", {
          day: "numeric",
          month: "short",
          year: "numeric",
          timeZone: "UTC",
        }).formatRange(start, end)
      : new Intl.DateTimeFormat("ru-RU", {
          month: "long",
          year: "numeric",
          timeZone: "UTC",
        }).format(month);
  const mine = data.tasks.filter((t) => isAssigned(t, data.sessionId) && t.deadlineAt);
  const projectTasks = mine.filter((t) => !projectId || t.projectId === projectId);
  const statuses = useMemo(() => {
    const projects = data.projects.filter((p) => !projectId || p.id === projectId);
    return projects
      .flatMap((project) =>
        project.columns.map((column) => ({
          id: column.id,
          name: column.name || statusLabels[column.id] || column.id,
        })),
      )
      .filter(
        (item, index, all) => all.findIndex((candidate) => candidate.id === item.id) === index,
      );
  }, [data.projects, projectId]);
  const visible = projectTasks.filter((task) => {
    if (status && task.status !== status) return false;
    if (deadlineFilter === "overdue")
      return task.status !== "done" && Date.parse(task.deadlineAt) < Date.parse(data.now);
    if (deadlineFilter === "today") return dayKey(task.deadlineAt) === today;
    if (deadlineFilter === "upcoming") {
      const key = dayKey(task.deadlineAt);
      return (
        Date.parse(task.deadlineAt) >= Date.parse(data.now) &&
        key >= today &&
        key <= upcomingLastKey
      );
    }
    return true;
  });
  const week = mine.filter(
    (t) =>
      t.status !== "done" &&
      Date.parse(t.deadlineAt) >= Date.parse(data.now) &&
      Date.parse(t.deadlineAt) < Date.parse(data.now) + 7 * 86400000,
  );
  const dayTasks = visible
    .filter((t) => {
      const key = dayKey(t.deadlineAt);
      if (selectedDay) return key === selectedDay;
      if (deadlineFilter === "upcoming") return true;
      return mode === "week"
        ? key >= firstKey && key <= lastKey
        : key.startsWith(anchor.slice(0, 7));
    })
    .sort(
      (a, b) =>
        (Date.parse(a.deadlineAt) - Date.parse(b.deadlineAt)) * (sortDirection === "asc" ? 1 : -1),
    );
  const resetFilters = () => {
    setProjectId("");
    setStatus("");
    setDeadlineFilter("");
    setSortDirection("asc");
  };
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
            <h2 aria-live="polite" aria-atomic="true">
              {mode === "week" && deadlineFilter === "upcoming"
                ? new Intl.DateTimeFormat("ru-RU", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                    timeZone: "UTC",
                  }).formatRange(start, gridEnd)
                : periodLabel}
            </h2>
            <span>МСК · UTC+3</span>
          </div>
          <div className="calendar-mode" role="group" aria-label="Вид календаря">
            {(["week", "month"] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={mode === value}
                onClick={() => {
                  setMode(value);
                  setSelectedDay("");
                }}
              >
                {value === "week" ? "Неделя" : "Месяц"}
              </button>
            ))}
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
          <label className="sr-only" htmlFor="calendar-deadline">
            Срок
          </label>
          <select
            id="calendar-deadline"
            value={deadlineFilter}
            onChange={(e) => {
              const value = e.target.value as typeof deadlineFilter;
              setDeadlineFilter(value);
              if (value === "upcoming") {
                setAnchor(today);
                setSelectedDay("");
              }
            }}
          >
            <option value="">Все сроки</option>
            <option value="overdue">Просроченные</option>
            <option value="today">Сегодня</option>
            <option value="upcoming">Ближайшие 7 дней</option>
          </select>
          <label className="sr-only" htmlFor="calendar-status">
            Статус
          </label>
          <select
            id="calendar-status"
            value={status}
            onChange={(e) => setStatus(e.target.value as Status | "")}
          >
            <option value="">Все статусы</option>
            {statuses.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <label className="sr-only" htmlFor="calendar-sort">
            Сортировка по сроку
          </label>
          <select
            id="calendar-sort"
            value={sortDirection}
            onChange={(e) => setSortDirection(e.target.value as typeof sortDirection)}
          >
            <option value="asc">Сначала ближайшие</option>
            <option value="desc">Сначала дальние</option>
          </select>
          <label className="calendar-date-picker">
            Перейти к дате
            <input
              type="date"
              value={anchor}
              onChange={(event) => {
                const value = event.target.value;
                if (
                  !/^\d{4}-\d{2}-\d{2}$/.test(value) ||
                  !Number.isFinite(Date.parse(`${value}T12:00:00Z`))
                )
                  return;
                setAnchor(value);
                setSelectedDay(value);
                setDeadlineFilter("");
              }}
            />
          </label>
          <div className="button-wrap">
            <Button
              variant="ghost"
              onClick={() => {
                setAnchor(today);
                setSelectedDay(dayKey(data.now));
                setDeadlineFilter("");
              }}
            >
              Сегодня
            </Button>
            <IconButton
              icon="back"
              label={mode === "week" ? "Предыдущая неделя" : "Предыдущий месяц"}
              onClick={() => navigate(-1)}
            />
            <IconButton
              icon="arrow"
              label={mode === "week" ? "Следующая неделя" : "Следующий месяц"}
              onClick={() => navigate(1)}
            />
          </div>
        </div>
        <CalendarSwipe className={`calendar-swipe calendar-${mode}`} onNavigate={navigate}>
          <div className="calendar-weekdays">
            {[
              "Понедельник",
              "Вторник",
              "Среда",
              "Четверг",
              "Пятница",
              "Суббота",
              "Воскресенье",
            ].map((d, index) => (
              <span key={d}>
                {d}
                <abbr>{["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][index]}</abbr>
              </span>
            ))}
          </div>
          <div className="calendar-grid">
            {Array.from({ length: cells }, (_, i) => {
              const date = new Date(Date.parse(start.toISOString()) + i * 86400000);
              const iso = date.toISOString();
              const key = dayKey(iso);
              const tasks = visible
                .filter((t) => dayKey(t.deadlineAt) === key)
                .sort(
                  (a, b) =>
                    (Date.parse(a.deadlineAt) - Date.parse(b.deadlineAt)) *
                    (sortDirection === "asc" ? 1 : -1),
                );
              return (
                <div
                  className={`calendar-cell ${mode === "month" && date.getUTCMonth() !== month.getUTCMonth() ? "outside" : ""} ${deadlineFilter === "upcoming" && (key < today || key > upcomingLastKey) ? "outside" : ""} ${key === dayKey(data.now) ? "today" : ""} ${selectedDay === key ? "selected" : ""}`}
                  key={key}
                >
                  <button
                    className="calendar-day-button"
                    onClick={() => setSelectedDay(selectedDay === key ? "" : key)}
                    aria-label={`${dateLabel(iso)}, ${plural(tasks.length)}`}
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
                        className={`calendar-task status-${t.status} deadline-${urgency(t, data.now)}`}
                        title={`${t.title} · ${data.projects.find((p) => p.id === t.projectId)?.columns.find((c) => c.id === t.status)?.name || statusLabels[t.status] || "Этап проекта"}${urgency(t, data.now) === "overdue" ? " · Просрочено" : ""}`}
                      >
                        <span aria-hidden="true" /> <strong>{t.title}</strong>
                        <small>
                          {data.projects
                            .find((p) => p.id === t.projectId)
                            ?.columns.find((c) => c.id === t.status)?.name ||
                            statusLabels[t.status] ||
                            "Этап проекта"}
                          {urgency(t, data.now) === "overdue" ? " · Просрочено" : ""}
                        </small>
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
        </CalendarSwipe>
        <p className="calendar-swipe-hint">
          {mode === "week"
            ? "Листай недели свайпом влево или вправо"
            : "Листай месяцы свайпом влево или вправо"}
        </p>
      </section>
      <section className="panel calendar-task-panel">
        <div className="panel-heading">
          <h2>
            {selectedDay
              ? `Задачи на ${dateLabel(`${selectedDay}T12:00:00+03:00`)}`
              : deadlineFilter === "upcoming"
                ? "Задачи на ближайшие 7 дней"
                : mode === "week"
                  ? "Задачи на эту неделю"
                  : "Задачи на этот месяц"}
          </h2>
          {selectedDay && (
            <Button variant="ghost" onClick={() => setSelectedDay("")}>
              {mode === "week" ? "Вся неделя" : "Весь месяц"}
            </Button>
          )}
          {(projectId || status || deadlineFilter) && (
            <Button variant="ghost" onClick={resetFilters}>
              Сбросить фильтры
            </Button>
          )}
        </div>
        {dayTasks.length ? (
          <TaskList tasks={dayTasks} />
        ) : (
          <EmptyState
            icon="calendar"
            title={selectedDay ? "На эту дату задач нет" : "На этот период задач нет"}
            description="Здесь появятся твои задачи со сроками на выбранные даты."
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
