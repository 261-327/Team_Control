"use client";

import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { useUi } from "@/providers/UiContext";
import { client } from "@/services/client";
import { canManage } from "@/lib/permissions";
import {
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
import type { Material } from "@/types/domain";

export function MaterialsView() {
  const { projectId } = useParams<{ projectId: string }>();
  const data = useReadyData();
  const ui = useUi();
  const [form, setForm] = useState<Material | "new" | null>(null);
  const [remove, setRemove] = useState<Material | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const materials = data.materials.filter((m) => m.projectId === projectId);
  const manage = canManage(data, projectId);
  return (
    <>
      <div className="section-heading section-top">
        <div>
          <h2>Материалы проекта</h2>
          <p className="muted">Ссылки на репозиторий, макеты и документы.</p>
        </div>
        {manage && (
          <div className="button-wrap">
            <Button variant="secondary" onClick={() => setUploadOpen(true)}>
              <Icon name="file" size={17} />
              Загрузить файл
            </Button>
            <Button onClick={() => setForm("new")}>
              <Icon name="plus" size={17} />
              Добавить ссылку
            </Button>
          </div>
        )}
      </div>
      <div className="materials-grid">
        {materials.map((m) => {
          const isFile = m.kind === "file";
          const host = isFile ? "" : new URL(m.url).hostname;
          const type = isFile
            ? "Файл проекта"
            : host.includes("github")
              ? "Код проекта"
              : host.includes("figma")
                ? "Дизайн и прототипы"
                : "Документ / ссылка";
          return (
            <article className="material-card" key={m.id}>
              <div className="material-top">
                <span
                  className={`material-icon ${host.includes("github") ? "neutral" : host.includes("figma") ? "lilac" : "sage"}`}
                >
                  <Icon
                    name={
                      host.includes("github") ? "box" : host.includes("figma") ? "projects" : "file"
                    }
                    size={25}
                  />
                </span>
                {manage && (
                  <div className="button-wrap">
                    {!isFile && (
                      <IconButton
                        icon="edit"
                        label={`Редактировать «${m.title}»`}
                        onClick={() => setForm(m)}
                      />
                    )}
                    <IconButton
                      icon="trash"
                      label={`Удалить «${m.title}»`}
                      onClick={() => setRemove(m)}
                    />
                  </div>
                )}
              </div>
              <span className="material-type">{type}</span>
              <h3>{m.title}</h3>
              <p>{m.description || "Без описания"}</p>
              {isFile ? (
                <a className="material-link" href={`/api/materials/${m.id}/download/`}>
                  <span>
                    <Icon name="download" size={15} />
                    {m.fileName || "Скачать файл"} · {formatFileSize(m.fileSize || 0)}
                  </span>
                  <Icon name="download" size={17} />
                </a>
              ) : (
                <a className="material-link" href={m.url} target="_blank" rel="noopener noreferrer">
                  <span>
                    <Icon name="link" size={15} />
                    {host}
                  </span>
                  <Icon name="upRight" size={17} />
                </a>
              )}
            </article>
          );
        })}
      </div>
      {!materials.length && (
        <section className="panel">
          <EmptyState
            icon="folder"
            title="Материалов пока нет"
            description="Добавьте ссылку на макеты, репозиторий или загрузите файл проекта."
            action={
              manage ? (
                <div className="button-wrap">
                  <Button variant="secondary" onClick={() => setUploadOpen(true)}>
                    <Icon name="file" size={16} />
                    Загрузить файл
                  </Button>
                  <Button onClick={() => setForm("new")}>
                    <Icon name="plus" size={16} />
                    Добавить ссылку
                  </Button>
                </div>
              ) : undefined
            }
          />
        </section>
      )}
      <div className="info-callout">
        <Icon name="lock" size={22} />
        <p>
          Файлы доступны только действующим участникам проекта. Разрешены PDF, PNG и JPEG до 10 МБ;
          скачивание проверяет доступ на сервере.
        </p>
      </div>
      {uploadOpen && (
        <MaterialFileUploadForm
          projectId={projectId}
          onClose={() => setUploadOpen(false)}
        />
      )}
      {form && (
        <MaterialForm
          key={typeof form === "string" ? "new" : form.id}
          projectId={projectId}
          material={typeof form === "string" ? undefined : form}
          onClose={() => setForm(null)}
        />
      )}{" "}
      {remove && (
        <ConfirmDialog
          title="Убрать материал из проекта?"
          description={remove.kind === "file"
            ? `Файл «${remove.fileName || remove.title}» и его запись будут удалены из проекта.`
            : `Ссылка «${remove.title}» исчезнет из этого списка. Сам документ останется во внешнем сервисе.`}
          onClose={() => setRemove(null)}
          onConfirm={async () => {
            await client.deleteMaterial(remove.id);
            ui.notify("Материал убран из проекта");
          }}
        />
      )}
    </>
  );
}
function MaterialForm({
  projectId,
  material,
  onClose,
}: {
  projectId: string;
  material?: Material;
  onClose: () => void;
}) {
  const ui = useUi();
  const action = useAction();
  const [title, setTitle] = useState(material?.title || "");
  const [url, setUrl] = useState(material?.url || "");
  const [description, setDescription] = useState(material?.description || "");
  return (
    <Modal
      title={material ? "Редактировать материал" : "Новый материал"}
      description="Название, ссылка и короткое описание материала."
      onClose={onClose}
      busy={action.busy}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void action.run(
            () => client.saveMaterial(projectId, { title, url, description }, material?.id),
            () => {
              ui.notify("Материал сохранён");
              onClose();
            },
          );
        }}
      >
        <Field label="Название" required>
          <input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Например, макеты личного кабинета"
            maxLength={255}
            required
          />
        </Field>
        <Field label="Ссылка" hint="Абсолютный адрес с https:// или http://" required>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://…"
            required
          />
        </Field>
        <Field label="Описание">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Что команда найдёт по этой ссылке?"
            maxLength={2000}
          />
        </Field>
        <FormError error={action.error} />
        <div className="form-actions">
          <Button type="button" variant="secondary" onClick={onClose} disabled={action.busy}>
            Отмена
          </Button>
          <Button loading={action.busy}>{material ? "Сохранить" : "Добавить материал"}</Button>
        </div>
      </form>
    </Modal>
  );
}


function formatFileSize(size: number) {
  if (size < 1024) return `${size} Б`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} КБ`;
  return `${(size / (1024 * 1024)).toFixed(1)} МБ`;
}

function MaterialFileUploadForm({
  projectId,
  onClose,
}: {
  projectId: string;
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

  const close = () => {
    if (busy) controller.current?.abort();
    onClose();
  };

  return (
    <Modal
      title="Загрузить файл"
      description="PDF, PNG или JPEG. Максимальный размер — 10 МБ."
      onClose={close}
      busy={busy}
    >
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          if (!file || busy) return;
          const ext = file.name.split(".").pop()?.toLowerCase();
          if (!["pdf", "png", "jpg", "jpeg"].includes(ext || "")) {
            setError("Выберите файл PDF, PNG или JPEG.");
            return;
          }
          if (file.size <= 0 || file.size > 10 * 1024 * 1024) {
            setError("Файл должен быть больше 0 и не превышать 10 МБ.");
            return;
          }
          setBusy(true);
          setError("");
          setProgress(0);
          controller.current = new AbortController();
          try {
            await client.uploadMaterialFile(
              projectId,
              { title: title.trim() || file.name, description, file },
              setProgress,
              controller.current.signal,
            );
            ui.notify("Файл добавлен в материалы проекта");
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
        <Field label="Файл" hint="PDF, PNG, JPG или JPEG; до 10 МБ" required>
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
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
