"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { useUi } from "@/providers/UiContext";
import { client } from "@/services/client";
import { allowedTransitions, canManage } from "@/lib/permissions";
import {
  Avatar,
  Button,
  ConfirmDialog,
  EmptyState,
  Field,
  FormError,
  IconButton,
  Modal,
  useAction,
} from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import { dateLabel } from "@/lib/format";
import { Deadline, StatusBadge } from "./TaskViews";

export function TaskDetailView() {
  const { projectId, taskId } = useParams<{ projectId: string; taskId: string }>();
  const data = useReadyData();
  const ui = useUi();
  const router = useRouter();
  const [tab, setTab] = useState("comments");
  const [comment, setComment] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [returnOpen, setReturnOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [deleting, setDeleting] = useState(false);
  const action = useAction();
  const commentsAction = useAction();
  const task = data.tasks.find((t) => t.id === taskId && t.projectId === projectId);
  const project = data.projects.find((p) => p.id === projectId);
  if (!task || !project)
    return (
      <EmptyState
        icon="lock"
        title="Задача недоступна"
        description="Проверь ссылку или попроси руководителя добавить тебя в команду."
        action={
          <Link href="/projects" className="btn btn-secondary">
            К моим проектам
          </Link>
        }
      />
    );
  const assignee = data.users.find((u) => u.id === task.assigneeId);
  const creator = data.users.find((u) => u.id === task.createdBy);
  const manage = canManage(data, projectId);
  const transitions = allowedTransitions(data, task);
  const comments = data.comments.filter((c) => c.taskId === task.id);
  const history = data.events.filter((e) => e.taskId === task.id);
  return (
    <div className="task-detail-page">
      <Link href={`/projects/${projectId}`} className="back-link">
        <Icon name="back" size={17} />К задачам проекта
      </Link>
      <div className="task-detail-heading">
        <div>
          <span className="eyebrow">ЗАДАЧА · SIP-{task.id.slice(0, 4).toUpperCase()}</span>
          <h1>{task.title}</h1>
          <div className="task-title-meta">
            <StatusBadge status={task.status} projectId={projectId} />
            <span className="tag">{task.tag}</span>
            <span>Создана {dateLabel(task.createdAt)}</span>
          </div>
        </div>
        {manage && (
          <div className="button-wrap">
            <Button variant="secondary" onClick={() => ui.openTask(projectId, task)}>
              <Icon name="edit" size={16} />
              Редактировать
            </Button>
            <IconButton icon="trash" label="Удалить задачу" onClick={() => setDeleting(true)} />
          </div>
        )}
      </div>
      <div className="task-detail-grid">
        <div>
          <section className="panel detail-description">
            <h2>О задаче</h2>
            <p className="pre-wrap">{task.description || "Описание пока не добавлено."}</p>
          </section>
          {(transitions.length > 0 ||
            task.resultUrl ||
            task.submittedAt ||
            task.status === "done") && (
            <section className="panel task-result">
              <div className="section-heading">
                <h2>
                  {task.status === "done"
                    ? "Результат принят"
                    : task.status === "in_review"
                      ? "Результат на проверке"
                      : "Следующий шаг"}
                </h2>
                <Icon name={task.status === "done" ? "checkCircle" : "flag"} size={20} />
              </div>
              {task.resultUrl && (
                <a
                  className="result-link"
                  href={task.resultUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <span>
                    <Icon name="link" size={18} />
                    {task.resultUrl}
                  </span>
                  <Icon name="upRight" size={17} />
                </a>
              )}
              {(task.submittedAt || task.acceptedAt) && (
                <p className="field-hint">
                  {[
                    task.submittedAt ? `Отправлено ${dateLabel(task.submittedAt, true)} МСК` : "",
                    task.acceptedAt ? `Принято ${dateLabel(task.acceptedAt, true)} МСК` : "",
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              )}
              {transitions.includes("in_review") && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void action.run(
                      () => client.transitionTask(task.id, "in_review", result ?? task.resultUrl),
                      () => ui.notify("Результат отправлен на проверку"),
                    );
                  }}
                >
                  <p className="muted">
                    Готово? Поделись результатом и передай задачу руководителю.
                  </p>
                  <Field
                    label="Ссылка на результат"
                    hint="Необязательно. Подойдут GitHub, Figma или документ"
                  >
                    <input
                      type="url"
                      placeholder="https://…"
                      value={result ?? task.resultUrl}
                      onChange={(e) => setResult(e.target.value)}
                    />
                  </Field>
                  <FormError error={action.error} />
                  <Button loading={action.busy}>
                    <Icon name="send" size={16} />
                    Отправить на проверку
                  </Button>
                </form>
              )}
              {transitions.includes("in_progress") && task.status === "todo" && (
                <>
                  <p className="muted">
                    Возьми задачу в работу, чтобы команда видела твой прогресс.
                  </p>
                  <FormError error={action.error} />
                  <Button
                    loading={action.busy}
                    onClick={() =>
                      void action.run(
                        () => client.transitionTask(task.id, "in_progress"),
                        () => ui.notify("Задача в работе"),
                      )
                    }
                  >
                    <Icon name="progress" size={16} />
                    Начать работу
                  </Button>
                </>
              )}
              {transitions.includes("done") && (
                <>
                  <p className="muted">
                    Проверь результат по критериям задачи. Если нужны правки, укажи, что доработать.
                  </p>
                  <FormError error={action.error} />
                  <div className="button-wrap">
                    <Button
                      loading={action.busy}
                      onClick={() =>
                        void action.run(
                          () => client.transitionTask(task.id, "done"),
                          () => ui.notify("Результат принят"),
                        )
                      }
                    >
                      <Icon name="check" size={17} />
                      Принять результат
                    </Button>
                    <Button
                      variant="secondary"
                      disabled={action.busy}
                      onClick={() => setReturnOpen(true)}
                    >
                      Вернуть на доработку
                    </Button>
                  </div>
                </>
              )}
            </section>
          )}
          <section className="panel discussion-panel">
            <div className="tabs">
              <button
                className={tab === "comments" ? "active" : ""}
                onClick={() => setTab("comments")}
              >
                Обсуждение <span className="count-pill">{comments.length}</span>
              </button>
              <button
                className={tab === "history" ? "active" : ""}
                onClick={() => setTab("history")}
              >
                История <span className="count-pill">{history.length}</span>
              </button>
            </div>
            {tab === "comments" ? (
              <>
                <div className="comments-list">
                  {comments.length ? (
                    comments.map((c) => {
                      const user = data.users.find((u) => u.id === c.userId);
                      return (
                        <article className="comment" key={c.id}>
                          <Avatar user={user} />
                          <div>
                            <header>
                              <strong>{user?.name || "Бывший участник"}</strong>
                              <time>{dateLabel(c.createdAt, true)} МСК</time>
                            </header>
                            <p className="pre-wrap">{c.text}</p>
                          </div>
                        </article>
                      );
                    })
                  ) : (
                    <div className="discussion-empty">
                      <Icon name="message" size={25} />
                      <p>
                        Комментариев пока нет.
                        <br />
                        Напиши вопрос или расскажи о ходе работы.
                      </p>
                    </div>
                  )}
                </div>
                <form
                  className="comment-form"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void commentsAction.run(
                      () => client.addComment(task.id, comment),
                      () => {
                        setComment("");
                        ui.notify("Комментарий добавлен");
                      },
                    );
                  }}
                >
                  <label className="sr-only" htmlFor="comment">
                    Твой комментарий
                  </label>
                  <textarea
                    id="comment"
                    placeholder="Обсудить задачу с командой…"
                    rows={3}
                    maxLength={2000}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                  />
                  <div>
                    <span>{comment.length}/2000 · МСК</span>
                    <Button loading={commentsAction.busy} disabled={!comment.trim()}>
                      <Icon name="send" size={15} />
                      Отправить
                    </Button>
                  </div>
                  <FormError error={commentsAction.error} />
                </form>
              </>
            ) : (
              <div className="history-list">
                {history.map((event) => (
                  <div key={event.id}>
                    <span className="history-dot" />
                    <div>
                      <p>
                        <strong>
                          {data.users.find((u) => u.id === event.userId)?.name || "Бывший участник"}
                        </strong>{" "}
                        {event.text}
                      </p>
                      <time>{dateLabel(event.createdAt, true)} МСК</time>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
        <aside className="task-detail-aside">
          <section className="panel task-properties">
            <h2>Детали задачи</h2>
            <dl>
              <div>
                <dt>Исполнитель</dt>
                <dd>
                  <Avatar user={assignee} size="xs" />
                  {assignee?.name || "Нужно назначить"}
                </dd>
              </div>
              <div>
                <dt>Срок выполнения</dt>
                <dd>
                  <Deadline task={task} />
                </dd>
                <dd className="exact-deadline">{dateLabel(task.deadlineAt, true)} МСК</dd>
              </div>
              <div>
                <dt>Проект</dt>
                <dd>
                  <Link href={`/projects/${projectId}`}>
                    <span className={`project-dot ${project.color}`} />
                    {project.name}
                  </Link>
                </dd>
              </div>
              <div>
                <dt>Автор</dt>
                <dd>
                  <Avatar user={creator} size="xs" />
                  {creator?.name || "Бывший участник"}
                </dd>
              </div>
              <div>
                <dt>Направление</dt>
                <dd>
                  <span className="tag">{task.tag}</span>
                </dd>
              </div>
            </dl>
          </section>
          <button
            className="task-ai-hint"
            onClick={() => ui.openAssistant(`Разбей на шаги задачу «${task.title}»`)}
          >
            <span>
              <Icon name="sparkles" size={23} />
            </span>
            <strong>Помощник по задаче</strong>
            <p>Помощник предложит список действий.</p>
            <span className="text-link">
              Спросить Сипи AI
              <Icon name="arrow" size={15} />
            </span>
          </button>
        </aside>
      </div>
      {returnOpen && (
        <Modal
          title="Вернуть на доработку"
          description="Помоги исполнителю понять, что нужно улучшить"
          onClose={() => setReturnOpen(false)}
          busy={action.busy}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void action.run(
                () => client.transitionTask(task.id, "in_progress", "", reason),
                () => {
                  setReturnOpen(false);
                  setReason("");
                  ui.notify("Задача возвращена в работу");
                },
              );
            }}
          >
            <Field label="Что нужно доработать?" required>
              <textarea
                autoFocus
                rows={5}
                maxLength={2000}
                placeholder="Опиши конкретные замечания…"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                required
              />
            </Field>
            <FormError error={action.error} />
            <div className="form-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setReturnOpen(false)}
                disabled={action.busy}
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
      {deleting && (
        <ConfirmDialog
          title="Удалить задачу?"
          description={`«${task.title}» и её обсуждение будут удалены из проекта.`}
          onClose={() => setDeleting(false)}
          onConfirm={async () => {
            await client.deleteTask(task.id);
            ui.notify("Задача удалена");
            router.push(`/projects/${projectId}`);
          }}
        />
      )}
    </div>
  );
}
