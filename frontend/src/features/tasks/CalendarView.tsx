"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { useUi } from "@/providers/UiContext";
import { Button, EmptyState, IconButton } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import { dayKey, dateLabel, plural } from "@/lib/format";
import { createCalendar } from "@/lib/calendar";
import {
  calendarPeriod,
  calendarSwipe,
  shiftCalendar,
  type CalendarMode,
} from "@/lib/calendar-navigation";
import { TaskList } from "./TaskViews";

export function CalendarView() {
  const data = useReadyData();
  const ui = useUi();
  const today = dayKey(data.now);
  const [anchor, setAnchor] = useState(today);
  const [mode, setMode] = useState<CalendarMode>("week");
  const [selectedDay, setSelectedDay] = useState("");
  const [projectId, setProjectId] = useState("");
  const gesture = useRef<{ x: number; y: number; time: number } | null>(null);
  const suppressClickUntil = useRef(0);
  const { start, end, month, cells } = calendarPeriod(anchor, mode);
  const firstKey = start.toISOString().slice(0, 10);
  const lastKey = end.toISOString().slice(0, 10);
  const navigate = (direction: number) => {
    setAnchor((value) => shiftCalendar(value, mode, direction));
    setSelectedDay("");
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
  const mine = data.tasks.filter((t) => t.assigneeId === data.sessionId && t.status !== "done");
  const visible = mine.filter((t) => !projectId || t.projectId === projectId);
  const week = mine.filter(
    (t) =>
      Date.parse(t.deadlineAt) >= Date.parse(data.now) &&
      Date.parse(t.deadlineAt) < Date.parse(data.now) + 7 * 86400000,
  );
  const dayTasks = visible
    .filter((t) => {
      const key = dayKey(t.deadlineAt);
      if (selectedDay) return key === selectedDay;
      return mode === "week"
        ? key >= firstKey && key <= lastKey
        : key.startsWith(anchor.slice(0, 7));
    })
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
            <h2 aria-live="polite" aria-atomic="true">
              {periodLabel}
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
          <div className="button-wrap">
            <Button
              variant="ghost"
              onClick={() => {
                setAnchor(today);
                setSelectedDay(dayKey(data.now));
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
        <div
          className={`calendar-swipe calendar-${mode}`}
          onTouchStart={(event) => {
            const touch = event.touches[0];
            // Leave edge gestures to browser back/forward navigation.
            gesture.current =
              event.touches.length === 1 &&
              touch.clientX > 24 &&
              touch.clientX < window.innerWidth - 24
                ? { x: touch.clientX, y: touch.clientY, time: event.timeStamp }
                : null;
          }}
          onTouchMove={(event) => {
            const initial = gesture.current;
            if (!initial) return;
            const touch = event.touches[0];
            if (
              event.touches.length !== 1 ||
              (Math.abs(touch.clientY - initial.y) > 12 &&
                Math.abs(touch.clientY - initial.y) > Math.abs(touch.clientX - initial.x))
            )
              gesture.current = null;
          }}
          onTouchCancel={() => {
            gesture.current = null;
          }}
          onTouchEnd={(event) => {
            const initial = gesture.current;
            gesture.current = null;
            if (!initial || event.touches.length || event.changedTouches.length !== 1) return;
            const touch = event.changedTouches[0];
            const direction = calendarSwipe(
              touch.clientX - initial.x,
              touch.clientY - initial.y,
              event.timeStamp - initial.time,
            );
            if (direction) {
              suppressClickUntil.current = performance.now() + 500;
              navigate(direction);
            }
          }}
          onClickCapture={(event) => {
            if (event.detail !== 0 && performance.now() < suppressClickUntil.current) {
              event.preventDefault();
              event.stopPropagation();
            }
          }}
        >
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
              const tasks = visible.filter((t) => dayKey(t.deadlineAt) === key);
              return (
                <div
                  className={`calendar-cell ${mode === "month" && date.getUTCMonth() !== month.getUTCMonth() ? "outside" : ""} ${key === dayKey(data.now) ? "today" : ""} ${selectedDay === key ? "selected" : ""}`}
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
        </div>
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
              : mode === "week"
                ? "Задачи на эту неделю"
                : "Задачи на этот месяц"}
          </h2>
          {selectedDay && (
            <Button variant="ghost" onClick={() => setSelectedDay("")}>
              {mode === "week" ? "Вся неделя" : "Весь месяц"}
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
