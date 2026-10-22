"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { client } from "@/services/client";
import { canManage } from "@/lib/permissions";
import { fromInputDate, toInputDate } from "@/lib/format";
import { Button, ConfirmDialog, Field, FormError, Modal, useAction } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import type {
  AssistantDraft,
  AssistantHistory,
  AssistantMode,
  AssistantTurn,
} from "@/types/domain";

const modes: { id: AssistantMode; label: string; icon: string }[] = [
  { id: "chat", label: "Помощник", icon: "sparkles" },
  { id: "tasks", label: "Черновик задач", icon: "tasks" },
  { id: "logo", label: "Логотип", icon: "image" },
];
const inFlight = (turn: AssistantTurn) => ["queued", "running"].includes(turn.status);

export function AssistantPanel({
  projectId,
  initialMessage,
  onClose,
}: {
  projectId?: string;
  initialMessage?: string;
  onClose: () => void;
}) {
  const data = useReadyData();
  const [selectedId, setSelectedId] = useState(projectId || "");
  return (
    <Modal
      title="Сипи AI"
      description="Помощник по твоим проектам"
      onClose={onClose}
      sheet
      focusSelector="#assistant-message"
    >
      <AssistantChat
        key={`${data.sessionId}:${selectedId}`}
        projectId={selectedId}
        initialMessage={initialMessage}
        onProjectChange={setSelectedId}
        onClose={onClose}
      />
    </Modal>
  );
}

function AssistantChat({
  projectId,
  initialMessage,
  onProjectChange,
  onClose,
}: {
  projectId: string;
  initialMessage?: string;
  onProjectChange: (id: string) => void;
  onClose: () => void;
}) {
  const data = useReadyData();
  const [turns, setTurns] = useState<AssistantTurn[]>([]);
  const [capabilities, setCapabilities] = useState<AssistantHistory["capabilities"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [pollError, setPollError] = useState("");
  const [mode, setMode] = useState<AssistantMode>("chat");
  const [message, setMessage] = useState(initialMessage || "");
  const [clearOpen, setClearOpen] = useState(false);
  const [reload, setReload] = useState(0);
  const action = useAction();
  const bottom = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const request = useRef<{ id: string; text: string; mode: AssistantMode } | null>(null);
  const pending = turns.find(inFlight);
  const pendingId = pending?.id;
  const busy = action.busy || !!pending;
  const ready = mode === "logo" ? capabilities?.imagesReady : capabilities?.chatReady;
  const updateTurn = useCallback((turn: AssistantTurn) => {
    setTurns((old) =>
      old.some((t) => t.id === turn.id)
        ? old.map((t) => (t.id === turn.id ? turn : t))
        : [...old, turn],
    );
  }, []);

  useEffect(() => {
    let active = true;
    client
      .assistantHistory(projectId || undefined)
      .then((history) => {
        if (!active) return;
        setTurns(history.turns);
        setCapabilities(history.capabilities);
        setLoadError("");
      })
      .catch((error: Error) => {
        if (active) setLoadError(error.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [projectId, reload]);

  useEffect(() => {
    if (!pendingId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const turn = await client.assistantTurn(pendingId);
        if (!active) return;
        updateTurn(turn);
        setPollError("");
        if (!inFlight(turn)) return;
      } catch (error) {
        if (!active) return;
        setPollError(error instanceof Error ? error.message : "Не удалось получить ответ.");
      }
      if (active) timer = setTimeout(poll, 2000);
    };
    timer = setTimeout(poll, 800);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [pendingId, updateTurn]); // Only the job identity controls polling.

  const last = turns.at(-1);
  useEffect(() => {
    if (!loading) textarea.current?.focus({ preventScroll: true });
  }, [loading]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "instant", block: "end" });
  }, [turns.length, last?.status]);

  const send = (text: string, chosenMode = mode) => {
    if (!text.trim() || busy || loading) return;
    if (
      !request.current ||
      request.current.text !== text.trim() ||
      request.current.mode !== chosenMode
    )
      request.current = { id: crypto.randomUUID(), text: text.trim(), mode: chosenMode };
    const current = request.current;
    void action.run(
      () => client.askAssistant(current.text, chosenMode, current.id, projectId || undefined),
      (turn) => {
        updateTurn(turn);
        request.current = null;
        setMessage("");
        textarea.current?.focus();
      },
    );
  };

  return (
    <>
      <div className="assistant-toolbar">
        <label htmlFor="assistant-project">Контекст</label>
        <select
          id="assistant-project"
          value={projectId}
          disabled={busy}
          onChange={(e) => onProjectChange(e.target.value)}
        >
          <option value="">Все мои проекты</option>
          {data.projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="icon-button"
          aria-label="Очистить историю помощника"
          disabled={busy || !turns.length}
          onClick={() => setClearOpen(true)}
        >
          <Icon name="trash" size={17} />
        </button>
      </div>
      <div className="assistant-mode-note">
        <span className={capabilities?.chatReady ? "live-dot" : "assistant-offline-dot"} />
        <strong>
          {loading
            ? "Подключение…"
            : capabilities?.chatReady
              ? "Помощник готов"
              : "Помощник недоступен"}
        </strong>
        <span>Данные проекта</span>
      </div>
      <div className="assistant-messages" aria-busy={loading}>
        <FormError error={loadError} />
        {loadError && (
          <Button variant="secondary" onClick={() => setReload((n) => n + 1)}>
            Повторить подключение
          </Button>
        )}
        {loading && <p role="status">Загружаем переписку…</p>}
        {!loading && !loadError && !turns.length && (
          <div className="assistant-welcome">
            <span className="assistant-orb">
              <Icon name="sparkles" size={28} />
            </span>
            <h3>С чего начнём?</h3>
            <p>
              Могу создать проект, добавить задачи на доску или разобраться в том, что уже есть.
            </p>
            <div className="assistant-prompts">
              {[
                {
                  title: "Что осталось до сдачи?",
                  mode: "chat" as const,
                  icon: "calendar",
                  text: "Что осталось сделать по проекту? Покажи ближайшие сроки и задачи, которым нужно внимание.",
                },
                {
                  title: projectId ? "Добавить задачи на доску" : "Начать новый проект",
                  mode: "chat" as const,
                  icon: "plus",
                  text: projectId
                    ? "Создай 5 задач по описанию проекта."
                    : "Создай проект «Название» — здесь опиши идею. Добавь 5 задач для начала работы.",
                },
                {
                  title: "Идея для логотипа",
                  mode: "logo" as const,
                  icon: "image",
                  text: "Придумай и нарисуй простой логотип по описанию проекта: лаконичный знак, чистый фон, без надписей.",
                },
              ].map((p) => (
                <button
                  key={p.title}
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setMode(p.mode);
                    setMessage(p.text);
                    textarea.current?.focus();
                  }}
                >
                  <span>
                    <Icon name={p.icon} size={19} />
                  </span>
                  {p.title}
                  <Icon name="arrow" size={15} />
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((turn) => (
          <div className="assistant-turn" key={turn.id}>
            <article className="chat-message chat-user">
              <p className="pre-wrap">{turn.message}</p>
            </article>
            {turn.status === "succeeded" && (
              <article className="chat-message chat-assistant">
                <div className="chat-author">
                  <span>
                    <Icon name="sparkles" size={15} />
                  </span>
                  <strong>Сипи AI</strong>
                </div>
                <p className="pre-wrap">{turn.reply.text}</p>
                {turn.reply.created && (
                  <div
                    className="assistant-receipt"
                    aria-label="Результат создания"
                    role="status"
                    aria-live="polite"
                  >
                    <div className="assistant-receipt-heading">
                      <span>
                        <Icon name="checkCircle" size={20} />
                      </span>
                      <div>
                        <strong>{turn.reply.created.projectName}</strong>
                        <p>
                          {turn.reply.created.kind === "create_project"
                            ? "Проект создан"
                            : "Задачи на доске"}
                        </p>
                      </div>
                    </div>
                    {!!turn.reply.created.tasks.length && (
                      <ul>
                        {turn.reply.created.tasks.map((task) => (
                          <li key={task.id}>
                            <Link href={task.href} onClick={onClose}>
                              <Icon name="circle" size={16} />
                              <span>{task.title}</span>
                              <Icon name="upRight" size={14} />
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                    <Link
                      className="btn btn-secondary"
                      href={turn.reply.created.href}
                      onClick={onClose}
                    >
                      Открыть проект <Icon name="arrow" size={16} />
                    </Link>
                  </div>
                )}
                {!!turn.reply.sources?.length && (
                  <div className="assistant-sources" aria-label="Источники ответа">
                    {turn.reply.sources.map((source, i) => (
                      <Link key={`${source.href}:${i}`} href={source.href} onClick={onClose}>
                        <Icon name="upRight" size={14} />
                        {source.title}
                      </Link>
                    ))}
                  </div>
                )}
                {!!turn.reply.drafts?.length && (
                  <DraftPlan
                    turn={turn}
                    projectId={projectId}
                    onSaved={updateTurn}
                    onClose={onClose}
                  />
                )}
                {turn.reply.imageUrl && (
                  <figure className="assistant-generated-image">
                    <Image
                      src={turn.reply.imageUrl}
                      alt="Концепт логотипа по описанию проекта"
                      width={512}
                      height={512}
                      unoptimized
                    />
                    <figcaption>Концепт логотипа · 512 × 512</figcaption>
                    <a
                      className="button button-secondary"
                      href={turn.reply.imageUrl}
                      download={`sipi-logo-${turn.id}.png`}
                    >
                      Скачать PNG
                    </a>
                  </figure>
                )}
              </article>
            )}
            {turn.status === "failed" && (
              <div className="assistant-turn-error" role="alert">
                <p>{turn.error}</p>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setMode(turn.mode);
                    setMessage(turn.message);
                    textarea.current?.focus();
                  }}
                >
                  Повторить запрос
                </button>
              </div>
            )}
            {turn.status === "cancelled" && (
              <p className="assistant-turn-cancelled">Запрос отменён.</p>
            )}
          </div>
        ))}
        {pending && (
          <div className="assistant-pending" role="status">
            <div className="assistant-thinking">
              <span>
                <Icon name="sparkles" size={16} />
              </span>
              <i />
              <i />
              <i />
              <span>
                {pending.status === "queued"
                  ? "Запрос в очереди…"
                  : pending.mode === "logo"
                    ? "Рисуем концепт…"
                    : "Готовим ответ…"}
              </span>
            </div>
            <p>
              {pending.mode === "logo"
                ? "Генерация картинки может занять несколько минут."
                : "Первый ответ может занять больше времени: модель загружается в память."}{" "}
              Чат можно закрыть — ответ сохранится.
            </p>
            <button
              type="button"
              disabled={action.busy}
              onClick={() =>
                void action.run(() => client.cancelAssistantTurn(pending.id), updateTurn)
              }
            >
              Отменить запрос
            </button>
          </div>
        )}
        <FormError error={pollError} />
        <div ref={bottom} />
      </div>
      <div className="assistant-composer">
        <div className="assistant-modes" role="group" aria-label="Режим помощника">
          {modes.map((m) => (
            <button
              key={m.id}
              type="button"
              aria-pressed={mode === m.id}
              disabled={busy}
              onClick={() => setMode(m.id)}
            >
              <Icon name={m.icon} size={15} />
              {m.label}
            </button>
          ))}
        </div>
        {!loading && !ready && !loadError && (
          <div className="assistant-setup-note" role="status">
            {mode === "logo"
              ? "Генератор изображений сейчас недоступен. Его нужно запустить на сервере Сипи."
              : "Не удалось подключиться к помощнику. Проверь запуск сервера и попробуй ещё раз."}
            <button type="button" disabled={busy} onClick={() => setReload((n) => n + 1)}>
              Проверить подключение
            </button>
          </div>
        )}
        {mode === "tasks" && !projectId && (
          <p className="assistant-hint">
            Выбери проект в поле «Контекст», чтобы подготовить задачи.
          </p>
        )}
        <FormError error={action.error} />
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(message);
          }}
        >
          <label className="sr-only" htmlFor="assistant-message">
            Сообщение помощнику
          </label>
          <textarea
            id="assistant-message"
            ref={textarea}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                send(message);
              }
            }}
            placeholder={
              mode === "tasks"
                ? "Опиши проект и что нужно подготовить…"
                : mode === "logo"
                  ? "Какой логотип ты представляешь?"
                  : "Создай проект, добавь задачи или задай вопрос…"
            }
            rows={2}
            maxLength={4000}
            disabled={busy || loading}
          />
          <button
            className="send-message"
            disabled={
              !message.trim() || busy || loading || !ready || (mode === "tasks" && !projectId)
            }
            aria-label="Отправить сообщение"
          >
            {action.busy ? <span className="spinner" /> : <Icon name="arrow" size={20} />}
          </button>
        </form>
        <div className="assistant-composer-footer">
          <span>Enter — отправить · Shift+Enter — новая строка</span>
          <span>{message.length}/4000</span>
        </div>
        <p className="assistant-disclaimer">
          <Icon name="lock" size={11} />
          По просьбе «создай» помощник сразу добавит проект или задачи.
        </p>
      </div>
      {clearOpen && (
        <ConfirmDialog
          title="Очистить переписку?"
          description="Сообщения, черновики и картинки будут удалены. Созданные задачи останутся на доске."
          confirmLabel="Очистить"
          onClose={() => setClearOpen(false)}
          onConfirm={async () => {
            await client.clearAssistantHistory(projectId || undefined);
            setTurns([]);
            setClearOpen(false);
          }}
        />
      )}
    </>
  );
}

function DraftPlan({
  turn,
  projectId,
  onSaved,
  onClose,
}: {
  turn: AssistantTurn;
  projectId: string;
  onSaved: (turn: AssistantTurn) => void;
  onClose: () => void;
}) {
  const data = useReadyData();
  const [drafts, setDrafts] = useState(() =>
    (turn.reply.drafts || []).map((draft) => ({ ...draft, selected: true })),
  );
  const action = useAction();
  const editable = canManage(data, projectId);
  const members = data.memberships.filter(
    (m) =>
      m.projectId === projectId &&
      m.role !== "teacher" &&
      data.users.find((u) => u.id === m.userId)?.kind !== "teacher",
  );
  const update = (index: number, patch: Partial<AssistantDraft & { selected: boolean }>) =>
    setDrafts((old) => old.map((d, i) => (i === index ? { ...d, ...patch } : d)));
  const selected = drafts.filter((d) => d.selected);
  if (turn.confirmedAt)
    return (
      <div className="assistant-created-tasks" role="status">
        <strong>
          <Icon name="checkCircle" size={17} />
          Задачи созданы
        </strong>
        {turn.reply.taskIds?.map((id) => {
          const task = data.tasks.find((t) => t.id === id);
          return task ? (
            <Link href={`/projects/${projectId}/tasks/${id}`} key={id} onClick={onClose}>
              {task.title}
              <Icon name="upRight" size={14} />
            </Link>
          ) : (
            <span key={id}>Задача удалена с доски</span>
          );
        })}
      </div>
    );
  return (
    <section className="assistant-plan" aria-label="Черновик задач">
      <h4>Проверь задачи перед созданием</h4>
      <p>
        Можно изменить текст, выбрать исполнителей и убрать лишнее. На доске пока ничего не
        изменилось.
      </p>
      {drafts.map((draft, index) => (
        <details className="assistant-draft" key={index} open={index === 0 ? true : undefined}>
          <summary>
            <span>
              {index + 1}. {draft.title}
            </span>
            <Icon name="down" size={16} />
          </summary>
          <div className="assistant-draft-fields">
            <label className="assistant-draft-select">
              <input
                type="checkbox"
                checked={draft.selected}
                disabled={!editable || action.busy}
                onChange={(e) => update(index, { selected: e.target.checked })}
              />
              Создать эту задачу
            </label>
            <Field label={`Название задачи ${index + 1}`}>
              <input
                maxLength={255}
                value={draft.title}
                disabled={!editable || action.busy}
                onChange={(e) => update(index, { title: e.target.value })}
              />
            </Field>
            <Field label={`Описание задачи ${index + 1}`}>
              <textarea
                rows={3}
                maxLength={10000}
                value={draft.description}
                disabled={!editable || action.busy}
                onChange={(e) => update(index, { description: e.target.value })}
              />
            </Field>
            <Field label={`Исполнитель задачи ${index + 1}`}>
              <select
                value={draft.assigneeId}
                disabled={!editable || action.busy}
                onChange={(e) => update(index, { assigneeId: e.target.value })}
              >
                <option value="">Выбери участника</option>
                {members.map((m) => (
                  <option key={m.userId} value={m.userId}>
                    {data.users.find((u) => u.id === m.userId)?.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={`Срок задачи ${index + 1}`}>
              <input
                type="datetime-local"
                value={toInputDate(draft.deadlineAt)}
                disabled={!editable || action.busy}
                onChange={(e) =>
                  update(index, { deadlineAt: e.target.value ? fromInputDate(e.target.value) : "" })
                }
              />
            </Field>
            <Field label={`Направление задачи ${index + 1}`}>
              <input
                maxLength={60}
                value={draft.tag}
                disabled={!editable || action.busy}
                onChange={(e) => update(index, { tag: e.target.value })}
              />
            </Field>
          </div>
        </details>
      ))}
      <FormError error={action.error} />
      {editable ? (
        <>
          {selected.some((d) => !d.assigneeId) && (
            <p className="assistant-hint">Выбери исполнителя для каждой выбранной задачи.</p>
          )}
          <Button
            disabled={!selected.length || selected.some((d) => !d.assigneeId || !d.title.trim())}
            loading={action.busy}
            onClick={() =>
              void action.run(
                () =>
                  client.confirmAssistantTasks(
                    turn.id,
                    selected.map((draft) => ({
                      title: draft.title,
                      description: draft.description,
                      assigneeId: draft.assigneeId,
                      deadlineAt: draft.deadlineAt,
                      tag: draft.tag,
                    })),
                  ),
                onSaved,
              )
            }
          >
            Создать выбранные задачи ({selected.length})
          </Button>
        </>
      ) : (
        <p className="assistant-hint">Сохранить задачи на доску может руководитель проекта.</p>
      )}
    </section>
  );
}
