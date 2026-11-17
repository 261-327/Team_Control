"use client";
import { useParams } from "next/navigation";
import { useReadyData } from "@/providers/DataProvider";
import { projectStatistics } from "@/lib/project-statistics";
import { EmptyState } from "@/components/ui";

export function ProjectStatisticsView() {
  const { projectId } = useParams<{ projectId: string }>();
  const data = useReadyData();
  if (!data.projects.some((project) => project.id === projectId)) {
    return (
      <EmptyState
        icon="lock"
        title="Проект недоступен"
        description="Нет права просмотра проекта."
      />
    );
  }
  const stats = projectStatistics(data, projectId);
  return (
    <section
      aria-label="Статистика задач проекта"
      className="panel"
      style={{ padding: 24, minWidth: 0 }}
    >
      <h2>Статистика задач</h2>
      <p className="muted">
        Все задачи проекта, независимо от фильтров доски. Обновляется вместе с задачами.
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
          gap: 16,
          margin: "24px 0",
        }}
      >
        {[
          ["Всего задач", stats.total],
          ["Выполнено", stats.completed],
          ["Активных", stats.active],
          ["Просрочено", stats.overdue],
          ["Без срока", stats.withoutDeadline],
          ["Выполнение", `${stats.completionPercent}%`],
        ].map(([label, value]) => (
          <div key={label}>
            <span className="muted">{label}</span>
            <p style={{ fontSize: 28, fontWeight: 700 }}>{value}</p>
          </div>
        ))}
      </div>
      <progress
        aria-label="Доля выполненных задач"
        value={stats.completionPercent}
        max={100}
        style={{ width: "100%" }}
      />
      {!stats.total && <p>В проекте пока нет задач. Все показатели равны нулю.</p>}
      <h3 style={{ marginTop: 24 }}>По этапам</h3>
      <ul>
        {stats.statuses.map((status) => (
          <li
            key={status.id}
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 16,
              padding: "10px 0",
              overflowWrap: "anywhere",
            }}
          >
            <span>{status.name}</span>
            <strong>{status.count}</strong>
          </li>
        ))}
      </ul>
      <h3 style={{ marginTop: 24 }}>По участникам</h3>
      <p className="muted">
        Задача с несколькими исполнителями учитывается у каждого один раз; в общей сводке — один
        раз. Выполненными считаются задачи этапа «Готово» (done), как в обзоре команд. Остальные
        этапы, включая пользовательские, считаются активными. Просрочка — срок строго раньше
        серверного времени.
      </p>
      <div style={{ overflowX: "auto", marginTop: 16 }}>
        <table style={{ width: "100%", minWidth: 480 }}>
          <caption>Назначения участников проекта</caption>
          <thead>
            <tr>
              {["Участник", "Всего", "Выполнено", "Просрочено"].map((label) => (
                <th key={label} scope="col" style={{ textAlign: "left", padding: 10 }}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {stats.members.map((member) => (
              <tr key={member.userId}>
                <th scope="row" style={{ textAlign: "left", padding: 10 }}>
                  {data.users.find((user) => user.id === member.userId)?.name || "Участник"}
                </th>
                <td>{member.total}</td>
                <td>{member.completed}</td>
                <td>{member.overdue}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ marginTop: 16 }}>
        Без исполнителя: {stats.unassigned.total}. С назначениями вне текущего состава:{" "}
        {stats.formerAssignees.total}.
      </p>
      <p className="muted">
        Назначения вне состава входят в общую сводку, но не в строки текущих участников. Суммы по
        участникам могут превышать общее число задач.
      </p>
    </section>
  );
}
