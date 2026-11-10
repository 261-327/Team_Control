"use client";

import { useState } from "react";
import { Button, ConfirmDialog, IconButton } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import { useReadyData } from "@/providers/DataProvider";
import { client } from "@/services/client";
import { canManage } from "@/lib/permissions";
import { formatFileSize } from "@/lib/attachments";
import { MaterialFileUploadForm } from "@/features/projects/MaterialFileUploadForm";
import type { Material } from "@/types/domain";

export function TaskAttachments({ projectId, taskId }: { projectId: string; taskId: string }) {
  const data = useReadyData();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [remove, setRemove] = useState<Material | null>(null);
  const files = data.materials.filter(
    (file) => file.projectId === projectId && file.taskId === taskId && file.kind === "file",
  );
  return (
    <section className="panel task-attachments" aria-label="Файлы задачи">
      <div className="section-heading">
        <h2>
          Файлы <span className="count-pill">{files.length}</span>
        </h2>
        <Button variant="secondary" onClick={() => setUploadOpen(true)}>
          <Icon name="paperclip" size={17} /> Прикрепить файл
        </Button>
      </div>
      {files.length ? (
        <ul className="attachment-list">
          {files.map((file) => (
            <li key={file.id}>
              <Icon name="file" size={20} />
              <a href={`/api/materials/${file.id}/download/`}>
                <strong>{file.title || file.fileName}</strong>
                <span>
                  {formatFileSize(file.fileSize || 0)} ·{" "}
                  {data.users.find((user) => user.id === file.createdBy)?.name ||
                    "Участник проекта"}
                </span>
              </a>
              {(file.createdBy === data.sessionId || canManage(data, projectId)) && (
                <IconButton
                  icon="trash"
                  label={`Удалить файл «${file.title}»`}
                  onClick={() => setRemove(file)}
                />
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Прикрепи задание, документ или скриншот. До 3 МБ на файл.</p>
      )}
      {uploadOpen && (
        <MaterialFileUploadForm
          projectId={projectId}
          taskId={taskId}
          onClose={() => setUploadOpen(false)}
        />
      )}
      {remove && (
        <ConfirmDialog
          title="Удалить файл?"
          description={`Файл «${remove.fileName || remove.title}» будет удалён из задачи и материалов проекта.`}
          onClose={() => setRemove(null)}
          onConfirm={async () => {
            await client.deleteMaterial(remove.id);
            setRemove(null);
          }}
        />
      )}
    </section>
  );
}
