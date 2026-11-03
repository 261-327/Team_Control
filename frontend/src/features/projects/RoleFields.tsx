"use client";
import { useState } from "react";
import { Field, Button, Modal, FormError, useAction } from "@/components/ui";
import { professions } from "@/lib/format";
import { useReadyData } from "@/providers/DataProvider";
import { useUi } from "@/providers/UiContext";
import { client } from "@/services/client";
import type { Profession, RoleInput } from "@/types/domain";

export function RoleFields({
  value,
  onChange,
}: {
  value: RoleInput;
  onChange: (value: RoleInput) => void;
}) {
  return (
    <>
      <Field label="Твоя роль в команде" required>
        <select
          value={
            value.profession === "developer" && ["ios", "android"].includes(value.specialization)
              ? `developer:${value.specialization}`
              : value.profession
          }
          onChange={(e) => {
            const [profession, specialization] = e.target.value.split(":");
            onChange({
              profession: profession as Profession,
              specialization: profession === "developer" ? specialization || "frontend" : "",
              customRole: profession === "other" ? value.customRole : "",
            });
          }}
        >
          <option value="developer:ios">Мобильный разработчик · iOS</option>
          <option value="developer:android">Мобильный разработчик · Android</option>
          {Object.entries(professions).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </Field>
      {value.profession === "developer" && (
        <Field label="Направление разработки" required>
          <select
            value={value.specialization}
            onChange={(e) => onChange({ ...value, specialization: e.target.value })}
            required
          >
            <option value="">Выбери направление</option>
            <option value="frontend">Фронтенд</option>
            <option value="backend">Бэкенд</option>
            <option value="ios">Мобильная разработка · iOS</option>
            <option value="android">Мобильная разработка · Android</option>
          </select>
        </Field>
      )}
      {value.profession === "other" && (
        <Field label="Своя роль" required>
          <input
            value={value.customRole}
            onChange={(e) => onChange({ ...value, customRole: e.target.value })}
            placeholder="Например, продакт-менеджер"
            maxLength={100}
            required
          />
        </Field>
      )}
    </>
  );
}
export const initialRole: RoleInput = {
  profession: "developer",
  specialization: "frontend",
  customRole: "",
};

export function RoleEditor({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const data = useReadyData();
  const membership = data.memberships.find(
    (m) => m.projectId === projectId && m.userId === data.sessionId,
  )!;
  const [role, setRole] = useState<RoleInput>({
    profession: membership?.profession ?? initialRole.profession,
    specialization: membership?.specialization ?? "",
    customRole: membership?.customRole ?? "",
  });
  const action = useAction();
  const ui = useUi();
  if (!membership)
    return (
      <Modal title="Моя роль в проекте" onClose={onClose}>
        <p role="alert">Ты больше не участвуешь в этом проекте.</p>
      </Modal>
    );
  return (
    <Modal
      title="Моя роль в проекте"
      description={data.projects.find((p) => p.id === projectId)?.name}
      onClose={onClose}
      busy={action.busy}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void action.run(
            () => client.updateMyRole(projectId, role),
            () => {
              ui.notify("Роль обновлена");
              onClose();
            },
          );
        }}
      >
        <RoleFields value={role} onChange={setRole} />
        <FormError error={action.error} />
        <div className="form-actions">
          <Button type="button" variant="secondary" onClick={onClose} disabled={action.busy}>
            Отмена
          </Button>
          <Button loading={action.busy}>Сохранить роль</Button>
        </div>
      </form>
    </Modal>
  );
}
