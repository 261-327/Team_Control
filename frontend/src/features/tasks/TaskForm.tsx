"use client";

import { useState } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { client } from "@/services/client";
import { canManage } from "@/lib/permissions";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  Field,
  FormError,
  Modal,
  useAction,
} from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import { fromInputDate, toInputDate } from "@/lib/format";
import type { Task } from "@/types/domain";

export function TaskForm({
  projectId,
  task,
  onClose,
  onSaved,
}: {
  projectId?: string;
  task?: Task;
  onClose: () => void;
  onSaved: () => void;
}) {
  const data = useReadyData();
  const projects = data.projects.filter((p) => canManage(data, p.id));
  const action = useAction();
  const [form, setForm] = useState({
    projectId: task?.projectId || projectId || projects[0]?.id || "",
    title: task?.title || "",
    description: task?.description || "",
    assigneeId: task?.assigneeId || "",
    deadline: task
      ? toInputDate(task.deadlineAt)
      : toInputDate(new Date(Date.parse(data.now) + 3 * 86400000).toISOString()),
    tag: task?.tag || "Команда",
  });
  const [initial] = useState(form);
  const [discard, setDiscard] = useState(false);
  const dirty = JSON.stringify(form) !== JSON.stringify(initial);
  const requestClose = () => {
    if (dirty) setDiscard(true);
    else onClose();
  };
  const pastDeadline =
    form.deadline && Date.parse(`${form.deadline}:00+03:00`) < Date.parse(data.now);
  const set = (key: keyof typeof form, value: string) =>
    setForm((f) => ({ ...f, [key]: value, ...(key === "projectId" ? { assigneeId: "" } : {}) }));
  const members = data.memberships.filter(
    (m) =>
      m.projectId === form.projectId &&
      m.role !== "teacher" &&
      data.users.find((u) => u.id === m.userId)?.kind !== "teacher",
  );
  return (
    <>
      <Modal
        title={task ? "Редактировать задачу" : "Новая задача"}
        description={
          task
            ? "Описание, исполнитель и срок выполнения."
            : "Укажи, что нужно сделать, кто отвечает и когда срок."
        }
        onClose={requestClose}
        busy={action.busy}
        wide
      >
        {!projects.length ? (
          <EmptyState
            icon="lock"
            title="Создание доступно руководителю"
            description="Попроси руководителя проекта добавить задачу или создай свой проект."
          />
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void action.run(async () => {
                if (!form.title.trim()) throw new Error("Введите название задачи.");
                if (!form.assigneeId) throw new Error("Выберите исполнителя.");
                if (!form.deadline) throw new Error("Укажите срок выполнения.");
                const input = {
                  projectId: form.projectId,
                  title: form.title,
                  description: form.description,
                  assigneeId: form.assigneeId,
                  deadlineAt: fromInputDate(form.deadline),
                  tag: form.tag,
                };
                if (task) await client.updateTask(task.id, input);
                else await client.createTask(input);
              }, onSaved);
            }}
          >
            <Field label="Название задачи" required>
              <input
                autoFocus
                placeholder="Что нужно сделать?"
                value={form.title}
                onChange={(e) => set("title", e.target.value)}
                maxLength={255}
                required
              />
            </Field>
            <Field label="Описание" hint="Контекст, ожидаемый результат и критерии готовности">
              <textarea
                rows={5}
                placeholder="Расскажи, какой результат ожидается…"
                value={form.description}
                onChange={(e) => set("description", e.target.value)}
                maxLength={10000}
              />
            </Field>
            <div className="form-grid">
              <Field label="Проект" required>
                <select
                  value={form.projectId}
                  disabled={!!task}
                  onChange={(e) => set("projectId", e.target.value)}
                >
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Исполнитель" required>
                <select
                  value={form.assigneeId}
                  onChange={(e) => set("assigneeId", e.target.value)}
                  required
                >
                  <option value="">Выбери участника</option>
                  {members.map((m) => (
                    <option key={m.userId} value={m.userId}>
                      {data.users.find((u) => u.id === m.userId)?.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Срок выполнения" hint="Московское время (UTC+3)" required>
                <input
                  type="datetime-local"
                  value={form.deadline}
                  onChange={(e) => set("deadline", e.target.value)}
                  required
                />
              </Field>
              <Field label="Направление">
                <select value={form.tag} onChange={(e) => set("tag", e.target.value)}>
                  {[
                    ...new Set([
                      form.tag,
                      "Команда",
                      "Дизайн",
                      "Фронтенд",
                      "Бэкенд",
                      "Аналитика",
                      "Исследование",
                      "Тестирование",
                    ]),
                  ].map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
              </Field>
            </div>
            {pastDeadline && (
              <p className="form-note warning-note">
                <Icon name="alert" size={16} />
                Этот срок уже прошёл. Задача будет отмечена как просроченная; её всё равно можно
                сохранить.
              </p>
            )}
            {!task && (
              <p className="form-note">
                <Icon name="circle" size={15} /> Новая задача появится в колонке «К выполнению»
              </p>
            )}
            <FormError error={action.error} />
            <div className="form-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={requestClose}
                disabled={action.busy}
              >
                Отмена
              </Button>
              <Button loading={action.busy}>
                <Icon name={task ? "check" : "plus"} size={17} />
                {task ? "Сохранить изменения" : "Создать задачу"}
              </Button>
            </div>
          </form>
        )}
      </Modal>
      {discard && (
        <ConfirmDialog
          title="Закрыть без сохранения?"
          description="В задаче есть изменения. Можно вернуться к форме и продолжить работу."
          confirmLabel="Не сохранять"
          onClose={() => setDiscard(false)}
          onConfirm={async () => onClose()}
        />
      )}
    </>
  );
}
