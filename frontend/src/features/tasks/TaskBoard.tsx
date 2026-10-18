"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import type { DragEvent } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { useUi } from "@/providers/UiContext";
import { client } from "@/services/client";
import { allowedBoardStatuses, canManage, canReorderTask } from "@/lib/permissions";
import { Avatar, Button, Field, FormError, IconButton, Modal, useAction } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import { statusLabels, statusIcon } from "@/lib/format";
import type { Status, Task } from "@/types/domain";
import { Deadline } from "./TaskViews";

type Move = { taskId: string; status: Status; beforeTaskId?: string };
export function TaskBoard({
  projectId,
  tasks,
  onColumnSettings,
  onCreate,
}: {
  projectId: string;
  tasks: Task[];
  onColumnSettings: (status: Status) => void;
  onCreate: () => void;
}) {
  const data = useReadyData();
  const ui = useUi();
  const action = useAction();
  const project = data.projects.find((p) => p.id === projectId)!;
  const manage = canManage(data, projectId);
  const [dragging, setDragging] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState("");
  const [returnMove, setReturnMove] = useState<Move | null>(null);
  const [reason, setReason] = useState("");
  const [lastMove, setLastMove] = useState<(Move & { reason?: string }) | null>(null);
  const perform = (move: Move, reason = "") => {
    setLastMove({ ...move, reason });
    void action.run(
      () => client.moveTask(move.taskId, move.status, move.beforeTaskId, reason),
      () => {
        setReturnMove(null);
        setReason("");
        setLastMove(null);
        ui.notify("Доска обновлена");
      },
    );
  };
  const requestMove = (move: Move) => {
    const task = data.tasks.find((t) => t.id === move.taskId && t.projectId === projectId);
    if (!task || action.busy || move.beforeTaskId === task.id) return;
    action.setError("");
    if (task.status === "in_review" && move.status === "in_progress") {
      setReturnMove(move);
      setReason("");
    } else perform(move);
  };
  const canDrop = (status: Status) => {
    const task = data.tasks.find((t) => t.id === dragging && t.projectId === projectId);
    return (
      !!task &&
      canReorderTask(data, task) &&
      (task.status === status || allowedBoardStatuses(data, task).includes(status))
    );
  };
  const dragOver = (event: DragEvent, status: Status, beforeTaskId?: string) => {
    if (action.busy || !canDrop(status)) return;
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = "move";
    setDropTarget(`${status}:${beforeTaskId || "end"}`);
  };
  const drop = (event: DragEvent, status: Status, beforeTaskId?: string) => {
    event.preventDefault();
    event.stopPropagation();
    const taskId = event.dataTransfer.getData("application/x-sipi-task") || dragging;
    if (taskId && canDrop(status)) requestMove({ taskId, status, beforeTaskId });
    setDragging(null);
    setDropTarget("");
  };
  return (
    <>
      {action.error && !returnMove && (
        <div className="board-error">
          <FormError error={action.error} />
          {lastMove && (
            <Button variant="secondary" onClick={() => perform(lastMove, lastMove.reason)}>
              Повторить
            </Button>
          )}
        </div>
      )}
      <div className="board-scroll">
        <div
          className="task-board"
          aria-busy={action.busy}
          style={{ gridTemplateColumns: `repeat(${project.columns.length}, minmax(226px, 1fr))` }}
        >
          {project.columns.map((col) => {
            const items = tasks
              .filter((t) => t.status === col.id)
              .sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
            const total = data.tasks.filter(
              (t) => t.projectId === projectId && t.status === col.id,
            ).length;
            return (
              <section
                key={col.id}
                data-status={col.id}
                className={`task-column column-${col.id} ${dragging && canDrop(col.id) ? "can-drop" : ""} ${dropTarget.startsWith(`${col.id}:`) ? "drop-active" : ""}`}
                aria-label={`Колонка ${col.name}`}
                onDragOver={(event) => dragOver(event, col.id)}
                onDrop={(event) => drop(event, col.id)}
              >
                <header>
                  <div>
                    <span className={`column-marker status-${col.id}`}>
                      <Icon name={statusIcon(col.id)} size={16} />
                    </span>
                    <h2>{col.name}</h2>
                    <span className="column-count">{items.length}</span>
                  </div>
                  {manage && (
                    <IconButton
                      icon="more"
                      label={`Настройки колонки «${col.name}»`}
                      onClick={() => onColumnSettings(col.id)}
                    />
                  )}
                </header>
                <div className="column-limit">
                  <span>
                    {total} / {col.limit}
                  </span>
                  <div>
                    <i style={{ width: `${(total / col.limit) * 100}%` }} />
                  </div>
                </div>
                <div className="column-cards">
                  {items.map((task) => (
                    <BoardCard
                      key={task.id}
                      task={task}
                      busy={action.busy}
                      dragging={dragging === task.id}
                      dropBefore={dropTarget === `${col.id}:${task.id}` && dragging !== task.id}
                      onMove={(status) => requestMove({ taskId: task.id, status })}
                      onDragStart={(event) => {
                        event.dataTransfer.setData("application/x-sipi-task", task.id);
                        event.dataTransfer.setData("text/plain", task.id);
                        event.dataTransfer.effectAllowed = "move";
                        setDragging(task.id);
                      }}
                      onDragEnd={() => {
                        setDragging(null);
                        setDropTarget("");
                      }}
                      onDragOver={(event) => dragOver(event, col.id, task.id)}
                      onDrop={(event) => drop(event, col.id, task.id)}
                    />
                  ))}
                  {!items.length && (
                    <div className="column-empty">
                      <Icon name={dragging && canDrop(col.id) ? "plus" : "tasks"} size={23} />
                      <span>
                        {dragging && canDrop(col.id)
                          ? "Перетащи задачу сюда"
                          : total > 0
                            ? "Нет задач по фильтрам"
                            : "Нет задач"}
                      </span>
                    </div>
                  )}
                </div>
                {manage && col.id === "todo" && (
                  <button className="add-card" onClick={onCreate}>
                    <Icon name="plus" size={16} />
                    Добавить задачу
                  </button>
                )}
              </section>
            );
          })}
        </div>
      </div>
      {returnMove && (
        <Modal
          title="Вернуть на доработку"
          description="Укажи, что нужно исправить в результате"
          onClose={() => {
            setReturnMove(null);
            action.setError("");
          }}
          busy={action.busy}
        >
          <form
            onSubmit={(event) => {
              event.preventDefault();
              perform(returnMove, reason);
            }}
          >
            <Field label="Что нужно доработать?" required>
              <textarea
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                rows={4}
                maxLength={2000}
                required
              />
            </Field>
            <FormError error={action.error} />
            <div className="form-actions">
              <Button
                type="button"
                variant="secondary"
                disabled={action.busy}
                onClick={() => {
                  setReturnMove(null);
                  action.setError("");
                }}
              >
                Отмена
              </Button>
              <Button loading={action.busy} disabled={!reason.trim()}>
                Вернуть в работу
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}

function BoardCard({
  task,
  busy,
  dragging,
  dropBefore,
  onMove,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
}: {
  task: Task;
  busy: boolean;
  dragging: boolean;
  dropBefore: boolean;
  onMove: (status: Status) => void;
  onDragStart: (event: DragEvent) => void;
  onDragEnd: () => void;
  onDragOver: (event: DragEvent) => void;
  onDrop: (event: DragEvent) => void;
}) {
  const data = useReadyData();
  const menu = useRef<HTMLDetailsElement>(null);
  const canDrag = canReorderTask(data, task) && !busy;
  const targets = allowedBoardStatuses(data, task);
  const comments = data.comments.filter((c) => c.taskId === task.id).length;
  const labels = data.projects.find((p) => p.id === task.projectId)!.columns;
  return (
    <article
      data-task-id={task.id}
      className={`task-card ${canDrag ? "is-draggable" : ""} ${dragging ? "is-dragging" : ""} ${dropBefore ? "drop-before" : ""}`}
      draggable={canDrag}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="task-card-top">
        <span
          className={`tag tag-${task.tag === "Дизайн" ? "lilac" : task.tag === "Бэкенд" ? "blue" : task.tag === "Аналитика" ? "sand" : "sage"}`}
        >
          {task.tag}
        </span>
        {targets.length ? (
          <details
            ref={menu}
            name="sipi-task-status"
            className="task-status-menu"
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                menu.current!.open = false;
                menu.current?.querySelector("summary")?.focus();
              }
            }}
            onBlur={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget))
                event.currentTarget.open = false;
            }}
          >
            <summary aria-label={`Изменить статус задачи «${task.title}»`} title="Изменить статус">
              <Icon name="more" size={18} />
            </summary>
            <div className="task-status-options" role="menu" aria-label="Статус задачи">
              <span>Статус</span>
              {labels
                .map((c) => c.id)
                .filter((s) => s === task.status || targets.includes(s))
                .map((status) => (
                  <button
                    key={status}
                    role="menuitem"
                    disabled={busy || status === task.status}
                    onClick={() => {
                      menu.current!.open = false;
                      onMove(status);
                    }}
                  >
                    <span className={`status-dot status-${status}`} />
                    {labels.find((c) => c.id === status)?.name || statusLabels[status]}
                    {status === task.status && <Icon name="check" size={14} />}
                  </button>
                ))}
            </div>
          </details>
        ) : (
          <span className="card-read-only" title="Просмотр задачи">
            <Icon name="upRight" size={15} />
          </span>
        )}
      </div>
      <Link
        className="task-card-link"
        href={`/projects/${task.projectId}/tasks/${task.id}`}
        draggable={false}
      >
        <h3>{task.title}</h3>
        <p>{task.description.split("\n")[0]}</p>
      </Link>
      <div className="task-card-id">
        SIP-{task.id.slice(0, 4).toUpperCase()}
        {comments > 0 && (
          <span>
            <Icon name="message" size={13} />
            {comments}
          </span>
        )}
      </div>
      <footer>
        <Deadline task={task} />
        <div className="card-assignee">
          {canDrag && (
            <span className="card-grip" title="Перетащить задачу">
              <svg
                width="12"
                height="16"
                viewBox="0 0 12 16"
                fill="currentColor"
                aria-hidden="true"
              >
                <circle cx="4" cy="4" r="1" />
                <circle cx="8" cy="4" r="1" />
                <circle cx="4" cy="8" r="1" />
                <circle cx="8" cy="8" r="1" />
                <circle cx="4" cy="12" r="1" />
                <circle cx="8" cy="12" r="1" />
              </svg>
            </span>
          )}
          <Avatar user={data.users.find((u) => u.id === task.assigneeId)} size="xs" />
        </div>
      </footer>
    </article>
  );
}
