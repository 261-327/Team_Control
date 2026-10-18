import type { Database, Status, Task } from "@/types/domain";
import { statuses } from "@/lib/format";

export function canAccess(db: Database, projectId: string, userId = db.sessionId) {
  const user = db.users.find((x) => x.id === userId);
  return (
    !!user &&
    (db.memberships.some((m) => m.projectId === projectId && m.userId === userId) ||
      !!user.scopeProjectIds?.includes(projectId))
  );
}
export function canManage(db: Database, projectId: string) {
  return (
    !!db.sessionId &&
    (db.memberships.some(
      (m) => m.projectId === projectId && m.userId === db.sessionId && m.role === "leader",
    ) ||
      !!db.users.find((u) => u.id === db.sessionId)?.scopeProjectIds?.includes(projectId))
  );
}
export function allowedTransitions(db: Database, task: Task): Status[] {
  if (!canAccess(db, task.projectId)) return [];
  const own =
    task.assigneeId === db.sessionId &&
    !db.memberships.some(
      (m) => m.projectId === task.projectId && m.userId === db.sessionId && m.role === "teacher",
    );
  if (own && task.status === "todo") return ["in_progress"];
  if (own && task.status === "in_progress") return ["in_review"];
  if (canManage(db, task.projectId) && task.status === "in_review") return ["done", "in_progress"];
  return [];
}
export function canOverview(db: Database) {
  return (
    db.memberships.some((m) => m.userId === db.sessionId && m.role !== "member") ||
    !!db.users.find((u) => u.id === db.sessionId)?.scopeProjectIds?.length ||
    db.users.find((u) => u.id === db.sessionId)?.kind === "staff"
  );
}

export function allowedBoardStatuses(db: Database, task: Task): Status[] {
  if (!canAccess(db, task.projectId)) return [];
  // Project managers can correct the board, including reopening a completed task.
  if (canManage(db, task.projectId))
    return (
      db.projects.find((p) => p.id === task.projectId)?.columns.map((c) => c.id) || statuses
    ).filter((status) => status !== task.status);
  return allowedTransitions(db, task);
}

export function canReorderTask(db: Database, task: Task) {
  return (
    canAccess(db, task.projectId) &&
    (canManage(db, task.projectId) ||
      (task.assigneeId === db.sessionId &&
        db.memberships.some(
          (m) =>
            m.projectId === task.projectId && m.userId === db.sessionId && m.role !== "teacher",
        )))
  );
}
