"use client";

import { useState } from "react";
import { Button, Field, FormError, Modal, useAction } from "@/components/ui";
import { useReadyData } from "@/providers/DataProvider";
import { useUi } from "@/providers/UiContext";
import { client } from "@/services/client";
import { canManage } from "@/lib/permissions";

export function ProjectPassport({ 
  projectId, 
  onClose 
}: { 
  projectId: string; 
  onClose: () => void 
}) {
  const data = useReadyData();
  const ui = useUi();
  const project = data.projects.find((p) => p.id === projectId)!;
  const manage = canManage(data, projectId);
  
  const [description, setDescription] = useState(project.description || "");
  const action = useAction();

  return (
    <Modal
      title="Паспорт проекта"
      description="Краткая справка о цели и результатах"
      onClose={onClose}
      busy={action.busy}
    >
      {manage ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(
              () => client.updateProjectDescription(projectId, description), 
              () => {
                ui.notify("Паспорт обновлен");
                onClose();
              }
            );
          }}
        >
          <Field label="Цель и ожидаемый результат" required>
            <textarea
              autoFocus
              rows={6}
              maxLength={10000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Опишите цель проекта..."
              required
            />
          </Field>
          <FormError error={action.error} />
          <div className="form-actions">
            <Button type="button" variant="secondary" onClick={onClose} disabled={action.busy}>
              Отмена
            </Button>
            <Button loading={action.busy}>Сохранить</Button>
          </div>
        </form>
      ) : (
        <div className="passport-readonly">
          <h3>Цель и ожидаемый результат</h3>
          <p className="pre-wrap">{project.description || "Описание пока не добавлено."}</p>
          <div className="form-actions">
            <Button type="button" variant="secondary" onClick={onClose}>
              Закрыть
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}