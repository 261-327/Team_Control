"use client";

import Link from "next/link";
import { useReadyData } from "@/providers/DataProvider";
import { canManage, canOverview } from "@/lib/permissions";
import { Avatar, EmptyState } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import { dateLabel, urgency } from "@/lib/format";

export function OverviewView() {
  const data = useReadyData();
  if (!canOverview(data))
    return (
      <EmptyState
        icon="lock"
        title="Обзор доступен руководителям и кураторам"
        description="Твои личные задачи и проекты находятся в основных разделах меню."
        action={
          <Link className="btn btn-secondary" href="/my-tasks">
            К моим задачам
          </Link>
        }
      />
    );
  const projects = data.projects.filter(
    (p) =>
      canManage(data, p.id) ||
      data.memberships.some(
        (m) => m.projectId === p.id && m.userId === data.sessionId && m.role === "teacher",
      ),
  );
  const ids = new Set(projects.map((p) => p.id));
  const tasks = data.tasks.filter((t) => ids.has(t.projectId));
  const active = tasks.filter((t) => t.status !== "done");
  const done = tasks.filter((t) => t.status === "done");
  const review = tasks.filter((t) => t.status === "in_review");
  const overdue = active.filter((t) => urgency(t, data.now) === "overdue");
  const workload = data.users
    .map((u) => ({ user: u, count: active.filter((t) => t.assigneeId === u.id).length }))
    .filter((u) => u.count)
    .sort((a, b) => b.count - a.count);
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>
            Обзор команд<span className="heading-dot">.</span>
          </h1>
          <p>Проекты, которые ты ведёшь или курируешь.</p>
        </div>
        {data.users.find((u) => u.id === data.sessionId)?.kind === "staff" && (
          <Link className="btn btn-primary" href="/projects/new">
            <Icon name="plus" size={17} />
            Учебный проект
          </Link>
        )}
      </div>
      <div className="stats-grid">
        {[
          { label: "В работе и в планах", count: active.length, icon: "tasks", tone: "sage" },
          { label: "На проверке", count: review.length, icon: "review", tone: "sand" },
          { label: "Просрочено", count: overdue.length, icon: "clock", tone: "peach" },
          { label: "Выполнено", count: done.length, icon: "checkCircle", tone: "lilac" },
        ].map((s) => (
          <div className="stat-card" key={s.label}>
            <div>
              <span>{s.label}</span>
              <strong>{String(s.count).padStart(2, "0")}</strong>
            </div>
            <span className={`stat-icon ${s.tone}`}>
              <Icon name={s.icon} size={22} />
            </span>
          </div>
        ))}
      </div>
      <div className="overview-grid">
        <section className="panel overview-projects">
          <div className="panel-heading">
            <h2>Состояние проектов</h2>
            <span className="count-pill">{projects.length}</span>
          </div>
          {projects.map((p) => {
            const all = tasks.filter((t) => t.projectId === p.id);
            const complete = all.filter((t) => t.status === "done").length;
            const late = all.filter((t) => urgency(t, data.now) === "overdue").length;
            const next = all
              .filter((t) => t.status !== "done")
              .sort((a, b) => Date.parse(a.deadlineAt) - Date.parse(b.deadlineAt))[0];
            return (
              <Link className="overview-project-row" href={`/projects/${p.id}`} key={p.id}>
                <span className={`project-icon ${p.color}`}>
                  <Icon name={p.symbol} />
                </span>
                <div>
                  <h3>{p.name}</h3>
                  <p>
                    {all.length - complete} в работе · {complete} готово
                    {late > 0 && <span className="overdue-inline"> · {late} просрочено</span>}
                  </p>
                  <div className={`progress-track ${p.color}`}>
                    <span style={{ width: `${all.length ? (complete / all.length) * 100 : 0}%` }} />
                  </div>
                </div>
                <div className="overview-next">
                  <strong>{all.length ? Math.round((complete / all.length) * 100) : 0}%</strong>
                  <span>
                    {next ? `Ближайший срок: ${dateLabel(next.deadlineAt)}` : "Нет открытых задач"}
                  </span>
                </div>
                <Icon name="chevron" size={18} />
              </Link>
            );
          })}
          {!projects.length && (
            <EmptyState
              icon="projects"
              title="Пока нет закреплённых проектов"
              description="Проекты появятся здесь после назначения куратора или руководителя."
            />
          )}
        </section>
        <section className="panel workload-panel">
          <div className="panel-heading">
            <h2>Задачи участников</h2>
            <Icon name="users" size={18} />
          </div>
          <p className="muted">Незавершённые задачи по участникам</p>
          {workload.map(({ user, count }) => (
            <div className="workload-row" key={user.id}>
              <Avatar user={user} size="xs" />
              <div>
                <strong>{user.name}</strong>
                <div className="progress-track">
                  <span
                    style={{
                      width: `${(count / Math.max(...workload.map((w) => w.count), 1)) * 100}%`,
                    }}
                  />
                </div>
              </div>
              <strong>{count}</strong>
            </div>
          ))}
          {!workload.length && <p className="muted">Пока нет активных назначений.</p>}
          <p className="field-hint">
            Количество задач не измеряет сложность работы или личный вклад человека.
          </p>
        </section>
      </div>
      <section className="panel overview-deadlines">
        <div className="panel-heading">
          <h2>Ближайшие дедлайны</h2>
          <span className="timezone">МСК, UTC+3</span>
        </div>
        {active
          .sort((a, b) => Date.parse(a.deadlineAt) - Date.parse(b.deadlineAt))
          .slice(0, 5)
          .map((t) => (
            <Link href={`/projects/${t.projectId}/tasks/${t.id}`} key={t.id}>
              <span
                className={`project-dot ${data.projects.find((p) => p.id === t.projectId)?.color}`}
              />
              <strong>{t.title}</strong>
              <span>{dateLabel(t.deadlineAt, true)}</span>
              <Avatar user={data.users.find((u) => u.id === t.assigneeId)} size="xs" />
              <Icon name="arrow" size={16} />
            </Link>
          ))}
        {!active.length && (
          <EmptyState
            icon="checkCircle"
            title="Нет открытых задач"
            description="Новые задачи появятся здесь вместе с дедлайнами."
          />
        )}
      </section>
    </>
  );
}
