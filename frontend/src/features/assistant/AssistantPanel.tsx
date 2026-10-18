"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { client } from "@/services/client";
import { FormError, Modal, useAction } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import type { AssistantReply } from "@/types/domain";
import { Deadline } from "@/features/tasks/TaskViews";

type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  reply?: AssistantReply;
};
const conversations = new Map<string, Message[]>();
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
  const key = `${data.sessionId}:${projectId || "personal"}`;
  const [messages, setMessages] = useState<Message[]>(conversations.get(key) || []);
  const [message, setMessage] = useState(initialMessage || "");
  const action = useAction();
  const bottom = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    conversations.set(key, messages);
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, key]);
  const send = (text: string) => {
    if (!text.trim() || action.busy) return;
    void action.run(
      () => client.askAssistant(text, projectId),
      (reply) => {
        setMessages((old) => [
          ...old,
          { id: crypto.randomUUID(), role: "user", text: text.trim() },
          { id: crypto.randomUUID(), role: "assistant", text: reply.text, reply },
        ]);
        setMessage("");
        textarea.current?.focus();
      },
    );
  };
  const selected = data.projects.find((p) => p.id === projectId);
  return (
    <Modal
      title="Сипи AI"
      description={selected ? selected.name : "Помощник в проектной работе"}
      onClose={onClose}
      sheet
      focusSelector="#assistant-message"
    >
      <div className="assistant-mode-note">
        <span className="live-dot" />
        <strong>ИИ пока не подключён</strong>
        <span>Сроки из твоих проектов</span>
      </div>
      <div className="assistant-messages" aria-live="polite" aria-relevant="additions text">
        {!messages.length && (
          <div className="assistant-welcome">
            <span className="assistant-orb">
              <Icon name="sparkles" size={28} />
            </span>
            <h3>Чем помочь?</h3>
            <p>Посмотреть срочные задачи и сроки на неделю. ИИ-агента подключим позже.</p>
            <div className="assistant-prompts">
              {[
                { icon: "clock", title: "Срочные задачи", text: "Что сейчас горит?" },
                { icon: "calendar", title: "Сроки на неделю", text: "Что у меня на неделе?" },
              ].map((prompt) => (
                <button key={prompt.title} disabled={action.busy} onClick={() => send(prompt.text)}>
                  <span>
                    <Icon name={prompt.icon} size={19} />
                  </span>
                  {prompt.title}
                  <Icon name="arrow" size={15} />
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <article className={`chat-message chat-${m.role}`} key={m.id}>
            {m.role === "assistant" && (
              <div className="chat-author">
                <span>
                  <Icon name="sparkles" size={15} />
                </span>
                <strong>Сипи AI</strong>
                <small>Сроки и задачи</small>
              </div>
            )}
            <p className="pre-wrap">{m.text}</p>
            {m.reply?.taskIds && (
              <div className="chat-tasks">
                {m.reply.taskIds.map((taskId) => {
                  const task = data.tasks.find((t) => t.id === taskId);
                  return task ? (
                    <Link
                      href={`/projects/${task.projectId}/tasks/${task.id}`}
                      key={taskId}
                      onClick={onClose}
                    >
                      <Icon name="tasks" size={16} />
                      <div>
                        <strong>{task.title}</strong>
                        <Deadline task={task} />
                      </div>
                      <Icon name="upRight" size={14} />
                    </Link>
                  ) : null;
                })}
              </div>
            )}
          </article>
        ))}
        {action.busy && (
          <div className="assistant-thinking" role="status">
            <span>
              <Icon name="sparkles" size={16} />
            </span>
            <i />
            <i />
            <i />
            <span>Подготовка ответа…</span>
          </div>
        )}
        <div ref={bottom} />
      </div>
      <div className="assistant-composer">
        <FormError error={action.error} />
        {messages.length > 0 && (
          <div className="assistant-quick-prompts">
            <button disabled={action.busy} onClick={() => send("Что сейчас горит?")}>
              Что горит?
            </button>
            <button disabled={action.busy} onClick={() => send("Что у меня на неделе?")}>
              Сроки на неделю
            </button>
          </div>
        )}
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
            autoFocus
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                send(message);
              }
            }}
            placeholder="Напиши сообщение…"
            rows={2}
            maxLength={4000}
            disabled={action.busy}
          />
          <button
            className="send-message"
            disabled={!message.trim() || action.busy}
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
          Помощник видит только доступные тебе проекты.
        </p>
      </div>
    </Modal>
  );
}
