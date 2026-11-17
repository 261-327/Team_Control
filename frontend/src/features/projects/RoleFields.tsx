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
  const standardDirections = ["frontend", "backend", "ios", "android"];
  const [customDirection, setCustomDirection] = useState(
    Boolean(value.specialization && !standardDirections.includes(value.specialization)),
  );
  return (
    <>
      <Field label="Роль в команде" required>
        <select
          value={
            value.profession === "developer" && ["ios", "android"].includes(value.specialization)
              ? `developer:${value.specialization}`
              : value.profession
          }
          onChange={(e) => {
            setCustomDirection(false);
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
        <>
          <Field label="Направление разработки" required>
            <select
              value={customDirection ? "__custom__" : value.specialization}
              onChange={(e) => {
                const custom = e.target.value === "__custom__";
                setCustomDirection(custom);
                onChange({ ...value, specialization: custom ? "" : e.target.value });
              }}
              required
            >
              <option value="">Выбери направление</option>
              <option value="frontend">Фронтенд</option>
              <option value="backend">Бэкенд</option>
              <option value="ios">Мобильная разработка · iOS</option>
              <option value="android">Мобильная разработка · Android</option>
              <option value="__custom__">Своё направление</option>
            </select>
          </Field>
          {customDirection && (
            <Field label="Своё направление разработки" required>
              <input
                value={value.specialization}
                onChange={(e) => onChange({ ...value, specialization: e.target.value })}
                placeholder="Например, разработка игр"
                maxLength={100}
                pattern={".*\\S.*"}
                required
              />
            </Field>
          )}
        </>
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

export function RoleEditor({
  projectId,
  userId,
  onClose,
}: {
  projectId: string;
  userId?: string;
  onClose: () => void;
}) {
  const data = useReadyData();
  const membership = data.memberships.find(
    (m) => m.projectId === projectId && m.userId === (userId || data.sessionId),
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
      <Modal
        title={
          userId && userId !== data.sessionId ? "Роль участника в проекте" : "Моя роль в проекте"
        }
        onClose={onClose}
      >
        <p role="alert">Участник больше недоступен в этом проекте.</p>
      </Modal>
    );
  return (
    <Modal
      title={
        userId && userId !== data.sessionId ? "Роль участника в проекте" : "Моя роль в проекте"
      }
      description={data.projects.find((p) => p.id === projectId)?.name}
      onClose={onClose}
      busy={action.busy}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void action.run(
            () =>
              userId && userId !== data.sessionId
                ? client.updateMemberRole(projectId, userId, role)
                : client.updateMyRole(projectId, role),
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
