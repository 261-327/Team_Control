import type { Database, Task } from "@/types/domain";
import { urgency } from "./format";

export function taskAssignees(task: Task) {
  return [...new Set(task.assigneeIds ?? (task.assigneeId ? [task.assigneeId] : []))];
}
export function summarizeTasks(tasks: Task[], now: string) {
  const completed = tasks.filter((task) => task.status === "done").length;
  return {
    total: tasks.length,
    completed,
    active: tasks.length - completed,
    overdue: tasks.filter((task) => urgency(task, now) === "overdue").length,
    withoutDeadline: tasks.filter((task) => !task.deadlineAt).length,
    completionPercent: tasks.length ? Math.round((completed / tasks.length) * 100) : 0,
  };
}
export function projectStatistics(data: Database, projectId: string) {
  const project = data.projects.find((item) => item.id === projectId);
  const tasks = data.tasks.filter((task) => task.projectId === projectId);
  const memberIds = [
    ...new Set(data.memberships.filter((m) => m.projectId === projectId).map((m) => m.userId)),
  ];
  const columns = [...(project?.columns ?? [])];
  for (const task of tasks) {
    if (!columns.some((column) => column.id === task.status)) {
      columns.push({ id: task.status, name: task.status, limit: 15 });
    }
  }
  return {
    ...summarizeTasks(tasks, data.now),
    statuses: columns.map((column) => ({
      id: column.id,
      name: column.name,
      count: tasks.filter((task) => task.status === column.id).length,
    })),
    members: memberIds.map((userId) => ({
      userId,
      ...summarizeTasks(
        tasks.filter((task) => taskAssignees(task).includes(userId)),
        data.now,
      ),
    })),
    unassigned: summarizeTasks(
      tasks.filter((task) => taskAssignees(task).length === 0),
      data.now,
    ),
    formerAssignees: summarizeTasks(
      tasks.filter((task) => taskAssignees(task).some((id) => !memberIds.includes(id))),
      data.now,
    ),
  };
}
