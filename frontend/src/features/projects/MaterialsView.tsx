"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
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
          <Button onClick={() => setForm("new")}>
            <Icon name="plus" size={17} />
            Добавить материал
          </Button>
        )}
      </div>
      <div className="materials-grid">
        {materials.map((m) => {
          const host = new URL(m.url).hostname;
          const type = host.includes("github")
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
                    <IconButton
                      icon="edit"
                      label={`Редактировать «${m.title}»`}
                      onClick={() => setForm(m)}
                    />
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
              <a className="material-link" href={m.url} target="_blank" rel="noopener noreferrer">
                <span>
                  <Icon name="link" size={15} />
                  {host}
                </span>
                <Icon name="upRight" size={17} />
              </a>
            </article>
          );
        })}
      </div>
      {!materials.length && (
        <section className="panel">
          <EmptyState
            icon="folder"
            title="Материалов пока нет"
            description="Добавьте ссылку на макеты, репозиторий или документ."
            action={
              manage ? (
                <Button onClick={() => setForm("new")}>
                  <Icon name="plus" size={16} />
                  Добавить первый материал
                </Button>
              ) : undefined
            }
          />
        </section>
      )}
      <div className="info-callout">
        <Icon name="link" size={22} />
        <p>
          Здесь хранятся ссылки. Документы открываются в своём сервисе; доступ к ним настраивается
          отдельно.
        </p>
      </div>
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
          description={`Ссылка «${remove.title}» исчезнет из этого списка. Сам документ останется во внешнем сервисе.`}
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
