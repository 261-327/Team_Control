"use client";

import Link from "next/link";
import { useState } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { useUi } from "@/providers/UiContext";
import { Avatar, Button, EmptyState } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import {
  dateLabel,
  dayKey,
  deadlineLabel,
  plural,
  statusLabels,
  statusIcon,
  statuses,
  urgency,
} from "@/lib/format";
import { canManage } from "@/lib/permissions";
import type { Snapshot, Status, Task } from "@/types/domain";

export function StatusBadge({ status, projectId }: { status: Status; projectId?: string }) {
  const data = useReadyData();
  const label =
    data.projects.find((p) => p.id === projectId)?.columns.find((c) => c.id === status)?.name ||
    statusLabels[status];
  return (
    <span className={`status-badge status-${status}`}>
      <Icon name={statusIcon(status)} size={14} />
      {label}
    </span>
  );
}
export function Deadline({ task }: { task: Task }) {
  const { now } = useReadyData();
  const level = urgency(task, now);
  return (
    <span
      className={`deadline deadline-${level}`}
      title={`${dateLabel(task.deadlineAt, true)} МСК${level === "overdue" ? " · Просрочено" : ""}`}
    >
      <Icon name={level === "overdue" ? "alert" : "calendar"} size={13} />
      {deadlineLabel(task, now)}
      {level === "overdue" && <span className="sr-only"> · Просрочено</span>}
    </span>
  );
}
export function TaskList({ tasks, showProject = true }: { tasks: Task[]; showProject?: boolean }) {
  const data = useReadyData();
  return (
    <ul className="task-list">
      {tasks.map((task) => {
        const project = data.projects.find((p) => p.id === task.projectId);
        const assignee = data.users.find((u) => u.id === task.assigneeId);
        return (
          <li key={task.id}>
            <Link
              className={`task-row ${task.status === "done" ? "task-completed" : ""}`}
              href={`/projects/${task.projectId}/tasks/${task.id}`}
              key={task.id}
            >
              <span
                className={`task-check status-${task.status}`}
                title={
                  data.projects
                    .find((p) => p.id === task.projectId)
                    ?.columns.find((c) => c.id === task.status)?.name || statusLabels[task.status]
                }
              >
                <span className="sr-only">
                  {data.projects
                    .find((p) => p.id === task.projectId)
                    ?.columns.find((c) => c.id === task.status)?.name || statusLabels[task.status]}
                </span>
                <Icon
                  name={
                    task.status === "done"
                      ? "checkCircle"
                      : task.status === "in_progress"
                        ? "progress"
                        : task.status === "in_review"
                          ? "review"
                          : "circle"
                  }
                  size={19}
                />
              </span>
              <div className="task-row-title">
                <strong>{task.title}</strong>
                <span>
                  {showProject && (
                    <>
                      <i className={`project-dot ${project?.color}`} />
                      {project?.name.split(" — ")[0]}
                      <span className="text-divider">/</span>
                    </>
                  )}
                  <span className="task-code">SIP-{task.id.slice(0, 4).toUpperCase()}</span>
                </span>
              </div>
              <span className="task-row-status">
                <StatusBadge status={task.status} projectId={task.projectId} />
              </span>
              <Deadline task={task} />
              <span className="task-row-assignee">
                <Avatar user={assignee} size="xs" />
              </span>
              <Icon name="chevron" size={15} className="row-chevron" />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
export type Filters = {
  query: string;
  status: string;
  assignee: string;
  period: string;
  mine: boolean;
};
export const defaultFilters: Filters = {
  query: "",
  status: "",
  assignee: "",
  period: "",
  mine: false,
};
export function filterTasks(tasks: Task[], filters: Filters, data: Snapshot) {
  return tasks
    .filter(
      (t) =>
        (!filters.query || t.title.toLowerCase().includes(filters.query.toLowerCase())) &&
        (!filters.status || t.status === filters.status) &&
        (!filters.assignee || t.assigneeId === filters.assignee) &&
        (!filters.mine || t.assigneeId === data.sessionId) &&
        (!filters.period ||
          (t.status !== "done" &&
            (filters.period === "overdue"
              ? urgency(t, data.now) === "overdue"
              : filters.period === "today"
                ? dayKey(t.deadlineAt) === dayKey(data.now)
                : Date.parse(t.deadlineAt) >= Date.parse(data.now) &&
                  Date.parse(t.deadlineAt) < Date.parse(data.now) + 7 * 86400000))),
    )
    .sort((a, b) => Date.parse(a.deadlineAt) - Date.parse(b.deadlineAt));
}
export function TaskFilters({
  filters,
  onChange,
  projectId,
  personal = false,
}: {
  filters: Filters;
  onChange: (value: Filters) => void;
  projectId?: string;
  personal?: boolean;
}) {
  const data = useReadyData();
  const [expanded, setExpanded] = useState(false);
  const active = Object.values(filters).some(Boolean);
  const set = (key: keyof Filters, value: string | boolean) =>
    onChange({ ...filters, [key]: value });
  return (
    <div className="task-filters">
      <div className="filter-top">
        <div className="search-field small">
          <Icon name="search" size={17} />
          <input
            aria-label="Найти задачу"
            placeholder="Найти задачу…"
            value={filters.query}
            onChange={(e) => set("query", e.target.value)}
          />
        </div>
        <Button
          variant="secondary"
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
          className={expanded ? "filter-selected" : ""}
        >
          <Icon name="filter" size={16} />
          Фильтры{active && <i className="filter-dot" />}
        </Button>
      </div>
      {expanded && (
        <div className="filter-options">
          <label>
            <span>Статус</span>
            <select
              aria-label="Фильтр по статусу"
              value={filters.status}
              onChange={(e) => set("status", e.target.value)}
            >
              <option value="">Все статусы</option>
              {(projectId
                ? data.projects.find((p) => p.id === projectId)?.columns.map((c) => c.id) ||
                  statuses
                : [
                    ...new Set([
                      ...statuses,
                      ...data.projects.flatMap((p) => p.columns.map((c) => c.id)),
                    ]),
                  ]
              ).map((s) => (
                <option key={s} value={s}>
                  {(projectId
                    ? data.projects.find((p) => p.id === projectId)?.columns.find((c) => c.id === s)
                        ?.name
                    : statusLabels[s] ||
                      data.projects.flatMap((p) => p.columns).find((c) => c.id === s)?.name) ||
                    statusLabels[s]}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Срок</span>
            <select
              aria-label="Фильтр по сроку"
              value={filters.period}
              onChange={(e) => set("period", e.target.value)}
            >
              <option value="">Любой срок</option>
              <option value="overdue">Просрочены</option>
              <option value="today">Сегодня</option>
              <option value="week">Ближайшие 7 дней</option>
            </select>
          </label>
          {!personal && (
            <>
              <label>
                <span>Исполнитель</span>
                <select
                  aria-label="Фильтр по исполнителю"
                  value={filters.assignee}
                  onChange={(e) => set("assignee", e.target.value)}
                >
                  <option value="">Все участники</option>
                  {data.memberships
                    .filter((m) => m.projectId === projectId && m.role !== "teacher")
                    .map((m) => (
                      <option key={m.userId} value={m.userId}>
                        {data.users.find((u) => u.id === m.userId)?.name}
                      </option>
                    ))}
                </select>
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={filters.mine}
                  onChange={(e) => set("mine", e.target.checked)}
                />
                Только мои
              </label>
            </>
          )}
          {active && (
            <Button variant="ghost" onClick={() => onChange(defaultFilters)}>
              Сбросить
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
export function ProjectMiniCard({ id }: { id: string }) {
  const data = useReadyData();
  const project = data.projects.find((p) => p.id === id)!;
  const tasks = data.tasks.filter((t) => t.projectId === id);
  const done = tasks.filter((t) => t.status === "done").length;
  const members = data.memberships.filter((m) => m.projectId === id && m.role !== "teacher");
  return (
    <Link href={`/projects/${id}`} className="project-mini-card">
      <div className="project-mini-top">
        <span className={`project-icon ${project.color}`}>
          <Icon name={project.symbol} />
        </span>
        <Icon name="upRight" size={17} />
      </div>
      <h3>{project.name}</h3>
      <p>
        {plural(tasks.length)} · {plural(members.length, ["участник", "участника", "участников"])}
      </p>
      <div className="project-progress-info">
        <span>Прогресс проекта</span>
        <strong>{tasks.length ? Math.round((done / tasks.length) * 100) : 0}%</strong>
      </div>
      <div className={`progress-track ${project.color}`}>
        <span style={{ width: `${tasks.length ? (done / tasks.length) * 100 : 0}%` }} />
      </div>
      <div className="project-mini-footer">
        <div className="avatar-stack">
          {members.slice(0, 4).map((m) => (
            <Avatar user={data.users.find((u) => u.id === m.userId)} key={m.userId} size="xs" />
          ))}
        </div>
        <span>
          {done} из {tasks.length} готово
        </span>
      </div>
    </Link>
  );
}

export function MyTasksView() {
  const data = useReadyData();
  const ui = useUi();
  const user = data.users.find((u) => u.id === data.sessionId)!;
  const [tab, setTab] = useState("attention");
  const [filters, setFilters] = useState(defaultFilters);
  const allMine = data.tasks.filter((t) => t.assigneeId === user.id);
  const active = allMine.filter((t) => t.status !== "done");
  const overdue = active.filter((t) => urgency(t, data.now) === "overdue");
  const today = active.filter((t) => dayKey(t.deadlineAt) === dayKey(data.now));
  const done = allMine.filter((t) => t.status === "done");
  const tasks = filterTasks(
    allMine.filter((t) =>
      tab === "done"
        ? t.status === "done"
        : tab === "all"
          ? true
          : t.status !== "done" &&
            !!t.deadlineAt &&
            Date.parse(t.deadlineAt) < Date.parse(data.now) + 7 * 86400000,
    ),
    filters,
    data,
  );
  const groups =
    tab === "attention"
      ? [
          {
            label: "Просрочено",
            tone: "red",
            tasks: tasks.filter((t) => urgency(t, data.now) === "overdue"),
          },
          {
            label: "Сегодня",
            tone: "orange",
            tasks: tasks.filter(
              (t) =>
                urgency(t, data.now) !== "overdue" && dayKey(t.deadlineAt) === dayKey(data.now),
            ),
          },
          {
            label: "На этой неделе",
            tone: "green",
            tasks: tasks.filter(
              (t) =>
                urgency(t, data.now) !== "overdue" && dayKey(t.deadlineAt) !== dayKey(data.now),
            ),
          },
        ]
      : [{ label: tab === "done" ? "Завершённые задачи" : "Все мои задачи", tone: "green", tasks }];
  const canCreate = data.projects.some((p) => canManage(data, p.id));
  const weekDays = Array.from({ length: 7 }, (_, index) => {
    const now = new Date(data.now);
    const weekday = (now.getUTCDay() + 6) % 7;
    return new Date(Date.parse(data.now) + (index - weekday) * 86400000).toISOString();
  });
  return (
    <div className="dashboard">
      <div className="workspace-greeting">
        <span>
          <Icon name="sun" size={17} />{" "}
          {new Intl.DateTimeFormat("ru-RU", {
            weekday: "long",
            day: "numeric",
            month: "long",
            timeZone: "Europe/Moscow",
          }).format(new Date(data.now))}
        </span>
        <span>Проектная деятельность</span>
      </div>
      <div className="page-heading">
        <div>
          <h1>Мои задачи</h1>
          <p>
            {plural(active.length)} в работе ·{" "}
            {plural(data.projects.length, ["проект", "проекта", "проектов"])}
          </p>
        </div>
        {canCreate && (
          <Button onClick={() => ui.openTask()}>
            <Icon name="plus" size={18} />
            Новая задача
          </Button>
        )}
      </div>
      {overdue.length > 0 && (
        <section className="deadline-summary">
          <span className="deadline-summary-icon">
            <Icon name="clock" size={21} />
          </span>
          <div>
            <h2>Есть задачи с прошедшим сроком</h2>
            <p>
              {overdue[0].title}
              {overdue.length > 1 ? ` и ещё ${overdue.length - 1}` : ""}
            </p>
          </div>
          <button
            onClick={() => {
              setTab("attention");
              setFilters({ ...defaultFilters, period: "overdue" });
            }}
          >
            Посмотреть
            <Icon name="arrow" size={16} />
          </button>
        </section>
      )}
      <section className="workspace-focus">
        <div className="workspace-focus-copy">
          <span className="workspace-eyebrow">Сипи AI</span>
          <h2>Создать проект с помощником</h2>
          <p>Опиши, что хотите сделать. Помощник создаст проект и добавит задачи на доску.</p>
          <button
            onClick={() =>
              ui.openAssistant(
                "Создай проект «Название» — здесь опиши идею. Добавь 5 задач для начала работы.",
              )
            }
          >
            Начать с помощником <Icon name="arrow" size={17} />
          </button>
        </div>
        <div className="workspace-focus-art" aria-hidden="true">
          <span className="focus-sun">
            <Icon name="sun" size={54} />
          </span>
          <div className="focus-task">
            <Icon name="checkCircle" size={18} />
            <span>Идея проекта</span>
            <i />
          </div>
          <div className="focus-task">
            <Icon name="circle" size={18} />
            <span>Первые задачи</span>
            <i />
          </div>
        </div>
      </section>
      <div className="stats-grid">
        {[
          {
            label: "Открыто",
            value: active.length,
            icon: "tasks",
            tone: "sage",
            text: "Во всех проектах",
          },
          {
            label: "На сегодня",
            value: today.length,
            icon: "sun",
            tone: "sand",
            text: "Срок сегодня",
          },
          {
            label: "Просрочено",
            value: overdue.length,
            icon: "clock",
            tone: "peach",
            text: "Срок уже прошёл",
          },
          {
            label: "Завершено",
            value: done.length,
            icon: "checkCircle",
            tone: "lilac",
            text: "Принято руководителем",
          },
        ].map((stat, index) => (
          <button
            key={stat.label}
            className="stat-card"
            onClick={() => {
              setTab(index === 3 ? "done" : index === 0 ? "all" : "attention");
              setFilters({
                ...defaultFilters,
                period: index === 1 ? "today" : index === 2 ? "overdue" : "",
              });
            }}
          >
            <div>
              <span>{stat.label}</span>
              <strong>{stat.value}</strong>
              <small>{stat.text}</small>
            </div>
            <span className={`stat-icon ${stat.tone}`}>
              <Icon name={stat.icon} size={22} />
            </span>
          </button>
        ))}
      </div>
      <div className="dashboard-columns">
        <div className="dashboard-primary">
          <section className="panel tasks-panel">
            <div className="panel-heading">
              <h2>
                Задачи <span className="count-pill">{active.length}</span>
              </h2>
              <span className="timezone">
                <Icon name="clock" size={13} />
                МСК, UTC+3
              </span>
            </div>
            <div className="tabs task-tabs">
              {[
                { id: "attention", label: "Требуют внимания" },
                { id: "all", label: "Все мои" },
                { id: "done", label: "Завершённые" },
              ].map((t) => (
                <button
                  key={t.id}
                  className={tab === t.id ? "active" : ""}
                  onClick={() => setTab(t.id)}
                >
                  {t.label}
                  {t.id === "attention" && overdue.length > 0 && <span className="tab-dot" />}
                </button>
              ))}
            </div>
            <TaskFilters filters={filters} onChange={setFilters} personal />
            {tasks.length ? (
              groups
                .filter((g) => g.tasks.length)
                .map((group) => (
                  <div className="task-group" key={group.label}>
                    <div className="task-group-label">
                      <span className={`group-dot ${group.tone}`} />
                      <strong>{group.label}</strong>
                      <span>{group.tasks.length}</span>
                    </div>
                    <TaskList tasks={group.tasks} />
                  </div>
                ))
            ) : (
              <EmptyState
                icon="checkCircle"
                title={
                  allMine.length ? "Нет задач по выбранным условиям" : "Пока нет назначенных задач"
                }
                description={
                  Object.values(filters).some(Boolean)
                    ? "По этим фильтрам задач нет. Попробуй сбросить условия."
                    : "Когда тебе назначат задачу, она появится здесь."
                }
                action={
                  Object.values(filters).some(Boolean) ? (
                    <Button variant="secondary" onClick={() => setFilters(defaultFilters)}>
                      Сбросить фильтры
                    </Button>
                  ) : (
                    <Link className="text-link" href="/projects">
                      Перейти к проектам <Icon name="arrow" size={15} />
                    </Link>
                  )
                }
              />
            )}
          </section>
          <section className="dashboard-projects">
            <div className="section-heading">
              <h2>
                Мои проекты <span className="count-pill">{data.projects.length}</span>
              </h2>
              <Link href="/projects" className="text-link">
                Все проекты
                <Icon name="arrow" size={16} />
              </Link>
            </div>
            <div className="mini-projects-grid">
              {data.projects.slice(0, 2).map((p) => (
                <ProjectMiniCard id={p.id} key={p.id} />
              ))}
              {!data.projects.length && (
                <Link href="/projects/search" className="project-create-placeholder">
                  <Icon name="search" />
                  Найти свою команду
                </Link>
              )}
            </div>
          </section>
        </div>
        <aside className="dashboard-aside">
          <section className="panel week-panel">
            <div className="panel-heading">
              <h2>Ближайшие сроки</h2>
              <Link href="/calendar" aria-label="Открыть календарь">
                <Icon name="upRight" size={17} />
              </Link>
            </div>
            <p className="week-month">
              {new Intl.DateTimeFormat("ru-RU", {
                month: "long",
                year: "numeric",
                timeZone: "Europe/Moscow",
              }).format(new Date(data.now))}{" "}
              <span>МСК</span>
            </p>
            <div className="week-strip">
              {weekDays.map((day, index) => (
                <Link
                  href="/calendar"
                  key={day}
                  className={dayKey(day) === dayKey(data.now) ? "current" : ""}
                >
                  <span>{["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][index]}</span>
                  <strong>{new Date(day).getUTCDate()}</strong>
                  <i
                    className={
                      active.some((t) => dayKey(t.deadlineAt) === dayKey(day)) ? "has-tasks" : ""
                    }
                  />
                </Link>
              ))}
            </div>
            <div className="upcoming-list">
              {active
                .filter((t) => !!t.deadlineAt && urgency(t, data.now) !== "overdue")
                .sort((a, b) => Date.parse(a.deadlineAt) - Date.parse(b.deadlineAt))
                .slice(0, 3)
                .map((t) => (
                  <Link key={t.id} href={`/projects/${t.projectId}/tasks/${t.id}`}>
                    <span
                      className={`upcoming-marker ${data.projects.find((p) => p.id === t.projectId)?.color}`}
                    />
                    <div>
                      <strong>{t.title}</strong>
                      <span>{dateLabel(t.deadlineAt, true)} МСК</span>
                    </div>
                  </Link>
                ))}
              {!active.length && <p className="muted">Здесь появятся ближайшие дедлайны.</p>}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
