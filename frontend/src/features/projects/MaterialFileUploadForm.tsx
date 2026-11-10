"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Field, FormError, Modal } from "@/components/ui";
import { useUi } from "@/providers/UiContext";
import { client } from "@/services/client";
import { FILE_ACCEPT, FILE_FORMATS, fileError } from "@/lib/attachments";

export function MaterialFileUploadForm({
  projectId,
  taskId,
  onClose,
}: {
  projectId: string;
  taskId?: string;
  onClose: () => void;
}) {
  const ui = useUi();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const close = () => {
    if (busy) controller.current?.abort();
    onClose();
  };

  return (
    <Modal
      title="Загрузить файл"
      description={`${FILE_FORMATS}. До 3 МБ на файл.`}
      onClose={close}
      busy={busy}
    >
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          if (!file || busy) return;
          const validation = fileError(file);
          if (validation) {
            setError(validation);
            return;
          }
          setBusy(true);
          setError("");
          setProgress(0);
          controller.current = new AbortController();
          try {
            await client.uploadMaterialFile(
              projectId,
              { title: title.trim() || file.name, description, file, taskId },
              setProgress,
              controller.current.signal,
            );
            ui.notify(taskId ? "Файл прикреплён к задаче" : "Файл добавлен в материалы проекта");
            onClose();
          } catch (cause) {
            if (!(cause instanceof DOMException && cause.name === "AbortError")) {
              setError(cause instanceof Error ? cause.message : "Не удалось загрузить файл.");
            }
          } finally {
            setBusy(false);
            controller.current = null;
          }
        }}
      >
        <Field label="Файл" hint={`${FILE_FORMATS}. До 3 МБ`} required>
          <input
            type="file"
            accept={FILE_ACCEPT}
            required
            disabled={busy}
            onChange={(event) => {
              const selected = event.target.files?.[0] || null;
              setFile(selected);
              if (selected && !title) setTitle(selected.name);
              setError("");
            }}
          />
        </Field>
        <Field label="Название материала">
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={255}
            placeholder="Например, техническое задание"
            disabled={busy}
          />
        </Field>
        <Field label="Описание">
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={2000}
            rows={3}
            placeholder="Кратко о содержимом файла"
            disabled={busy}
          />
        </Field>
        {busy && (
          <div className="file-upload-progress" aria-live="polite">
            <div className="file-upload-progress__label">
              <span>Загрузка файла</span>
              <strong>{progress}%</strong>
            </div>
            <progress value={progress} max={100} aria-label="Прогресс загрузки файла" />
          </div>
        )}
        <FormError error={error} />
        <div className="form-actions">
          {busy ? (
            <Button type="button" variant="secondary" onClick={() => controller.current?.abort()}>
              Отменить загрузку
            </Button>
          ) : (
            <Button type="button" variant="secondary" onClick={close}>
              Отмена
            </Button>
          )}
          <Button loading={busy} disabled={!file || busy}>
            Загрузить
          </Button>
        </div>
      </form>
    </Modal>
  );
}
