"use client";

import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { useUi } from "@/providers/UiContext";
import { client } from "@/services/client";
import { canManage } from "@/lib/permissions";
import {
  Avatar,
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
import { dateLabel, professions, plural, statusIcon } from "@/lib/format";
import {
  defaultFilters,
  filterTasks,
  ProjectMiniCard,
  TaskFilters,
  TaskList,
} from "@/features/tasks/TaskViews";
import { TaskBoard } from "@/features/tasks/TaskBoard";
import { useBoardPreference } from "@/lib/use-preference";
import type { Profession, RoleInput, Status } from "@/types/domain";

export function ProjectsView() {
  const data = useReadyData();
  const ui = useUi();
  const [query, setQuery] = useState("");
  const projects = data.projects.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()));
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Мои проекты</h1>
          <p>Проекты, в которых ты участвуешь.</p>
        </div>
        <Link className="btn btn-primary" href="/projects/new">
          <Icon name="plus" size={18} />
          Создать проект
        </Link>
      </div>
      <div className="projects-workspace-summary">
        <div>
          <strong>{data.projects.length}</strong>
          <span>
            {plural(data.projects.length, ["проект", "проекта", "проектов"]).replace(/^\d+\s*/, "")}{" "}
            в пространстве
          </span>
        </div>
        <p>Команда, задачи и материалы — в каждом проекте.</p>
        <button
          onClick={() =>
            ui.openAssistant(
              "Создай проект «Название» — здесь опиши идею. Добавь 5 задач для начала работы.",
            )
          }
        >
          <Icon name="sparkles" size={17} /> Создать с помощником <Icon name="arrow" size={16} />
        </button>
      </div>
      <div className="project-list-toolbar">
        <div className="search-field">
          <Icon name="search" size={18} />
          <input
            aria-label="Поиск моих проектов"
            placeholder="Найти свой проект…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Link href="/projects/search" className="text-link">
          <Icon name="compass" size={17} />
          Найти команду
        </Link>
      </div>
      <div className="projects-grid">
        {projects.map((p) => (
          <div className="project-list-card" key={p.id}>
            <ProjectMiniCard id={p.id} />
            <div className="project-list-description">
              <p>{p.description}</p>
              <span>
                <Icon name={canManage(data, p.id) ? "flag" : "user"} size={14} />
                {canManage(data, p.id)
                  ? "Руководитель проекта"
                  : data.memberships.find(
                        (m) => m.projectId === p.id && m.userId === data.sessionId,
                      )?.role === "teacher"
                    ? "Куратор проекта"
                    : "Участник команды"}
              </span>
            </div>
          </div>
        ))}
        {!query && (
          <Link href="/projects/new" className="project-create-placeholder">
            <span>
              <Icon name="plus" size={28} />
            </span>
            <h3>Новый проект</h3>
            <p>
              Создай проект и пригласи
              <br />
              участников команды
            </p>
            <span className="text-link">
              Создать проект
              <Icon name="arrow" size={15} />
            </span>
          </Link>
        )}
      </div>
      {query && !projects.length && (
        <EmptyState
          icon="search"
          title="Проект не найден"
          description="Попробуй другое название или найди новую команду через поиск проектов."
        />
      )}
    </>
  );
}
export function ProjectLayout({ children }: { children: React.ReactNode }) {
  const { projectId } = useParams<{ projectId: string }>();
  const data = useReadyData();
  const pathname = usePathname();
  const ui = useUi();
  const project = data.projects.find((p) => p.id === projectId);
  const members = data.memberships.filter((m) => m.projectId === projectId);
  const manage = canManage(data, projectId);
  if (!project)
    return (
      <EmptyState
        icon="lock"
        title="Проект недоступен"
        description="Ссылка могла измениться или у тебя пока нет доступа к команде."
        action={
          <Link href="/projects" className="btn btn-secondary">
            К моим проектам
          </Link>
        }
      />
    );
  if (pathname.includes("/tasks/")) return children;
  return (
    <div className="project-page">
      <Link href="/projects" className="back-link">
        <Icon name="back" size={16} />
        Все проекты
      </Link>
      <div className="project-heading">
        <span className={`project-icon large ${project.color}`}>
          <Icon name={project.symbol} size={30} />
        </span>
        <div className="project-heading-copy">
          <div className="project-title-row">
            <h1>{project.name}</h1>
            <span className="project-semester">Осень 2026</span>
          </div>
          <p>{project.description}</p>
        </div>
      </div>
      <div className="project-underheading">
        <div className="team-preview">
          <div className="avatar-stack">
            {members.slice(0, 4).map((m) => (
              <Avatar user={data.users.find((u) => u.id === m.userId)} key={m.userId} size="xs" />
            ))}
          </div>
          <Link href={`/projects/${projectId}/members`}>
            {members.length} в команде <Icon name="chevron" size={13} />
          </Link>
          <span className="vertical-divider" />
          <span className="muted">
            {manage ? "Ты руководишь этим проектом" : "Твоё пространство команды"}
          </span>
        </div>
        {manage && (
          <Button onClick={() => ui.openTask(projectId)}>
            <Icon name="plus" size={17} />
            Новая задача
          </Button>
        )}
      </div>
      <nav className="tabs project-tabs" aria-label="Разделы проекта">
        {[
          {
            path: "",
            label: "Задачи",
            icon: "board",
            count: data.tasks.filter((t) => t.projectId === projectId).length,
          },
          { path: "/members", label: "Команда", icon: "users", count: members.length },
          {
            path: "/materials",
            label: "Материалы",
            icon: "folder",
            count: data.materials.filter((m) => m.projectId === projectId).length,
          },
          { path: "/settings", label: "Настройки", icon: "settings", count: undefined },
        ].map((tab) => (
          <Link
            key={tab.path}
            href={`/projects/${projectId}${tab.path}`}
            className={pathname === `/projects/${projectId}${tab.path}` ? "active" : ""}
            aria-current={pathname === `/projects/${projectId}${tab.path}` ? "page" : undefined}
          >
            <Icon name={tab.icon} size={17} />
            {tab.label}
            {tab.count !== undefined && <span className="count-pill">{tab.count}</span>}
          </Link>
        ))}
      </nav>
      {children}
    </div>
  );
}
export function ProjectTasksView() {
  const { projectId } = useParams<{ projectId: string }>();
  const data = useReadyData();
  const ui = useUi();
  const [filters, setFilters] = useState(defaultFilters);
  const [view, setView] = useBoardPreference();
  const [column, setColumn] = useState<Status | null>(null);
  const allTasks = data.tasks.filter((t) => t.projectId === projectId);
  const tasks = filterTasks(allTasks, filters, data);
  const manage = canManage(data, projectId);
  return (
    <>
      <div className="board-toolbar">
        <TaskFilters filters={filters} onChange={setFilters} projectId={projectId} />
        <div className="view-switch" role="group" aria-label="Вид задач">
          <button
            className={view === "board" ? "active" : ""}
            aria-pressed={view === "board"}
            onClick={() => setView("board")}
          >
            <Icon name="board" size={16} />
            Доска
          </button>
          <button
            className={view === "list" ? "active" : ""}
            aria-pressed={view === "list"}
            onClick={() => setView("list")}
          >
            <Icon name="list" size={16} />
            Список
          </button>
        </div>
      </div>
      {view === "board" ? (
        <TaskBoard
          projectId={projectId}
          tasks={tasks}
          onColumnSettings={setColumn}
          onCreate={() => ui.openTask(projectId)}
        />
      ) : (
        <section className="panel project-task-list">
          <div className="task-list-header">
            <span>Задача</span>
            <span>Статус / срок / исполнитель</span>
          </div>
          {tasks.length ? (
            <TaskList tasks={tasks} showProject={false} />
          ) : (
            <EmptyState
              icon="tasks"
              title={allTasks.length ? "Нет совпадений" : "В проекте пока нет задач"}
              description={
                allTasks.length
                  ? "Попробуй изменить фильтры."
                  : "Добавь первую задачу и начни работу над проектом."
              }
              action={
                manage ? (
                  <Button onClick={() => ui.openTask(projectId)}>
                    <Icon name="plus" size={17} />
                    Создать задачу
                  </Button>
                ) : undefined
              }
            />
          )}
        </section>
      )}
      <div className="board-footnote">
        <span>
          <Icon name="clock" size={13} />
          Сроки — по московскому времени
        </span>
        <span>
          {plural(tasks.length)}
          {tasks.length !== allTasks.length ? ` из ${allTasks.length}` : ""}
        </span>
      </div>
      {column && (
        <ColumnEditor projectId={projectId} columnId={column} onClose={() => setColumn(null)} />
      )}
    </>
  );
}
export function ColumnEditor({
  projectId,
  columnId,
  onClose,
}: {
  projectId: string;
  columnId: Status;
  onClose: () => void;
}) {
  const data = useReadyData();
  const ui = useUi();
  const column = data.projects
    .find((p) => p.id === projectId)!
    .columns.find((c) => c.id === columnId)!;
  const [name, setName] = useState(column.name);
  const [limit, setLimit] = useState(column.limit);
  const action = useAction();
  const count = data.tasks.filter((t) => t.projectId === projectId && t.status === columnId).length;
  return (
    <Modal
      title="Настройки колонки"
      description="Понятное название и разумный объём работы"
      onClose={onClose}
      busy={action.busy}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void action.run(
            () => client.updateColumn(projectId, columnId, name, limit),
            () => {
              ui.notify("Настройки колонки сохранены");
              onClose();
            },
          );
        }}
      >
        <Field label="Название" required>
          <input
            autoFocus
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </Field>
        <Field
          label="Лимит задач"
          hint={`Сейчас в колонке: ${count}. Допустимый лимит: от 1 до 15.`}
          required
        >
          <input
            type="number"
            min={1}
            max={15}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            required
          />
        </Field>
        <p className="form-note">
          Четыре этапа сохраняют полный цикл: постановка → работа → проверка → приёмка.
        </p>
        <FormError error={action.error} />
        <div className="form-actions">
          <Button type="button" variant="secondary" onClick={onClose} disabled={action.busy}>
            Отмена
          </Button>
          <Button loading={action.busy}>Сохранить</Button>
        </div>
      </form>
    </Modal>
  );
}
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
          value={value.profession}
          onChange={(e) => onChange({ ...value, profession: e.target.value as Profession })}
        >
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
            <option value="ios">iOS</option>
            <option value="android">Android</option>
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
export function CreateProjectView() {
  const data = useReadyData();
  const router = useRouter();
  const ui = useUi();
  const action = useAction();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [role, setRole] = useState(initialRole);
  const [leader, setLeader] = useState(
    data.users.find((u) => u.id === data.sessionId)?.kind === "staff"
      ? data.users.find((u) => u.kind === "student")?.id || ""
      : data.sessionId || "",
  );
  const [teacher, setTeacher] = useState("");
  const staff = data.users.find((u) => u.id === data.sessionId)?.kind === "staff";
  return (
    <div className="narrow-page">
      <Link className="back-link" href="/projects">
        <Icon name="back" size={17} />
        Все проекты
      </Link>
      <div className="page-heading">
        <div>
          <h1>
            Новый проект<span className="heading-dot">.</span>
          </h1>
          <p>Укажи название, описание и свою роль в команде.</p>
        </div>
      </div>
      <section className="panel project-form-panel">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(
              () =>
                client.createProject(
                  name,
                  description,
                  role,
                  staff ? leader : undefined,
                  teacher || undefined,
                ),
              (project) => {
                ui.notify("Проект создан");
                router.push(`/projects/${project.id}`);
              },
            );
          }}
        >
          <div className="form-section-label">
            <span>01</span>
            <h2>О проекте</h2>
          </div>
          <Field label="Название проекта" required>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={255}
              placeholder="Например, Сервис навигации по кампусу"
              required
            />
          </Field>
          <Field
            label="Описание"
            hint="Цель проекта, для кого он и какой результат вы хотите получить"
          >
            <textarea
              rows={4}
              maxLength={10000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Мы создаём…"
            />
          </Field>
          <div className="form-section-label">
            <span>02</span>
            <h2>Команда</h2>
          </div>
          <div className="form-grid">
            <RoleFields value={role} onChange={setRole} />
          </div>
          {staff && (
            <>
              <Field label="Руководитель" required>
                <select value={leader} onChange={(e) => setLeader(e.target.value)} required>
                  <option value="">Выбери руководителя</option>
                  {data.users
                    .filter((u) => u.kind === "student")
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name}
                      </option>
                    ))}
                </select>
              </Field>
              <Field label="Преподаватель">
                <select value={teacher} onChange={(e) => setTeacher(e.target.value)}>
                  <option value="">Пока не назначен</option>
                  {data.users
                    .filter((u) => u.kind === "teacher")
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name}
                      </option>
                    ))}
                </select>
              </Field>
            </>
          )}
          <p className="form-note">
            <Icon name="users" size={17} />
            {staff
              ? "Руководитель и преподаватель получат доступ к новому проекту."
              : "Ты станешь руководителем проекта. Участников можно добавить после создания."}
          </p>
          <FormError error={action.error} />
          <div className="form-actions">
            <Link href="/projects" className="btn btn-secondary">
              Отмена
            </Link>
            <Button loading={action.busy}>
              <Icon name="plus" size={17} />
              Создать проект
            </Button>
          </div>
        </form>
      </section>
    </div>
  );
}
export function MembersView() {
  const { projectId } = useParams<{ projectId: string }>();
  const data = useReadyData();
  const ui = useUi();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [remove, setRemove] = useState("");
  const members = data.memberships.filter((m) => m.projectId === projectId);
  const manage = canManage(data, projectId);
  const invitations = data.invitations.filter(
    (i) => i.projectId === projectId && i.status === "pending",
  );
  const action = useAction();
  return (
    <>
      <div className="section-heading section-top">
        <div>
          <h2>Участники проекта</h2>
          <p className="muted">Состав команды и роли в этом проекте.</p>
        </div>
        {manage && (
          <Button onClick={() => setInviteOpen(true)}>
            <Icon name="plus" size={17} />
            Пригласить участника
          </Button>
        )}
      </div>
      <section className="panel members-panel">
        {members.map((m) => {
          const user = data.users.find((u) => u.id === m.userId)!;
          return (
            <div className="member-row" key={m.userId}>
              <Avatar user={user} size="md" />
              <div className="member-info">
                <strong>
                  {user.name}
                  {m.userId === data.sessionId && <span>это ты</span>}
                </strong>
                <span>{user.email}</span>
              </div>
              <div className="member-profession">
                <strong>
                  {m.profession === "other" ? m.customRole : professions[m.profession]}
                </strong>
                <span>
                  {m.specialization === "frontend"
                    ? "Фронтенд"
                    : m.specialization === "backend"
                      ? "Бэкенд"
                      : m.specialization === "ios"
                        ? "iOS"
                        : m.specialization === "android"
                          ? "Android"
                          : "Проектная команда"}
                </span>
              </div>
              <span className={`role-badge role-${m.role}`}>
                {m.role === "leader"
                  ? "Руководитель"
                  : m.role === "teacher"
                    ? "Преподаватель"
                    : "Участник"}
              </span>
              {manage && m.role !== "leader" && (
                <IconButton
                  icon="trash"
                  label={`Удалить ${user.name} из команды`}
                  onClick={() => setRemove(user.id)}
                />
              )}
            </div>
          );
        })}
      </section>
      {manage && invitations.length > 0 && (
        <section className="pending-invitations">
          <h3>
            Ожидают присоединения <span className="count-pill">{invitations.length}</span>
          </h3>
          {invitations.map((i) => (
            <div key={i.id}>
              <span className="invitation-mail">
                <Icon name="mail" size={18} />
              </span>
              <div>
                <strong>{i.email}</strong>
                <span>Приглашение · до {dateLabel(i.expiresAt)}</span>
              </div>
              <Link href={`/invitations/${i.id}`} className="text-link">
                Открыть ссылку
                <Icon name="upRight" size={14} />
              </Link>
              <IconButton
                icon="close"
                label={`Отменить приглашение ${i.email}`}
                disabled={action.busy}
                onClick={() =>
                  void action.run(
                    () => client.cancelInvitation(i.id),
                    () => ui.notify("Приглашение отменено"),
                  )
                }
              />
            </div>
          ))}
          <FormError error={action.error} />
        </section>
      )}
      <div className="info-callout">
        <Icon name="users" size={22} />
        <p>
          <strong>Роль относится к этому проекту.</strong> В другой команде у тебя может быть другая
          профессия и другие права.
        </p>
      </div>
      {inviteOpen && <InviteDialog projectId={projectId} onClose={() => setInviteOpen(false)} />}{" "}
      {remove && (
        <ConfirmDialog
          title="Убрать участника из команды?"
          description={`${data.users.find((u) => u.id === remove)?.name} потеряет доступ к этому проекту. Незавершённые задачи сначала нужно переназначить.`}
          confirmLabel="Убрать из команды"
          onClose={() => setRemove("")}
          onConfirm={async () => {
            await client.removeMember(projectId, remove);
            ui.notify("Состав команды обновлён");
          }}
        />
      )}
    </>
  );
}
function InviteDialog({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const [email, setEmail] = useState("");
  const [link, setLink] = useState("");
  const [copied, setCopied] = useState(false);
  const action = useAction();
  return (
    <Modal
      title={link ? "Приглашение готово" : "Пригласить участника"}
      description="Создай ссылку для участника. Принять её можно с указанной почтой."
      onClose={onClose}
      busy={action.busy}
    >
      {link ? (
        <div className="invite-success">
          <span className="success-icon">
            <Icon name="check" size={27} />
          </span>
          <p>
            Приглашение для <strong>{email}</strong>
          </p>
          <Field label="Ссылка на приглашение">
            <input readOnly value={link} onFocus={(e) => e.target.select()} />
          </Field>
          <Button
            onClick={() => {
              void action.run(
                async () => {
                  await navigator.clipboard.writeText(link);
                },
                () => setCopied(true),
              );
            }}
            variant="secondary"
          >
            <Icon name={copied ? "check" : "link"} size={16} />
            {copied ? "Скопировано" : "Скопировать ссылку"}
          </Button>
          <FormError error={action.error} />
          <p className="field-hint">
            Отправь эту ссылку участнику. Для входа ему понадобится аккаунт с указанной почтой.
          </p>
        </div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(
              () => client.invite(projectId, email),
              (invitation) => setLink(`${window.location.origin}/invitations/${invitation.id}`),
            );
          }}
        >
          <Field label="Почта участника" hint="Почта, с которой участник войдёт в Сипи" required>
            <input
              autoFocus
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </Field>
          <FormError error={action.error} />
          <div className="form-actions">
            <Button type="button" variant="secondary" onClick={onClose} disabled={action.busy}>
              Отмена
            </Button>
            <Button loading={action.busy}>
              <Icon name="mail" size={16} />
              Создать приглашение
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
export function ProjectSettingsView() {
  const { projectId } = useParams<{ projectId: string }>();
  const data = useReadyData();
  const ui = useUi();
  const router = useRouter();
  const project = data.projects.find((p) => p.id === projectId)!;
  const manage = canManage(data, projectId);
  const [column, setColumn] = useState<Status | null>(null);
  const [confirm, setConfirm] = useState("");
  return (
    <div className="settings-page">
      <section className="panel settings-panel">
        <h2>Этапы работы</h2>
        <p className="muted">Настрой названия этапов и допустимое количество задач в колонках.</p>
        {project.columns.map((c) => (
          <div className="column-settings-row" key={c.id}>
            <span className={`column-marker status-${c.id}`}>
              <Icon name={statusIcon(c.id)} size={18} />
            </span>
            <strong>{c.name}</strong>
            <span>
              {data.tasks.filter((t) => t.projectId === projectId && t.status === c.id).length} /{" "}
              {c.limit} задач
            </span>
            {manage && (
              <IconButton
                icon="edit"
                label={`Изменить колонку «${c.name}»`}
                onClick={() => setColumn(c.id)}
              />
            )}
          </div>
        ))}
      </section>
      <section className="panel settings-panel danger-zone">
        <h2>{manage ? "Удаление проекта" : "Участие в проекте"}</h2>
        <p>
          {manage
            ? "Проект, задачи и обсуждения будут удалены. Это действие нельзя отменить."
            : "После выхода проект исчезнет из твоего пространства. История твоих комментариев сохранится."}
        </p>
        <Button variant="danger" onClick={() => setConfirm(manage ? "delete" : "leave")}>
          <Icon name={manage ? "trash" : "logout"} size={17} />
          {manage ? "Удалить проект" : "Покинуть проект"}
        </Button>
      </section>
      {column && (
        <ColumnEditor projectId={projectId} columnId={column} onClose={() => setColumn(null)} />
      )}{" "}
      {confirm && (
        <ConfirmDialog
          title={confirm === "delete" ? `Удалить «${project.name}»?` : "Покинуть команду?"}
          description={
            confirm === "delete"
              ? "Все задачи, материалы и обсуждения проекта будут удалены."
              : "Твои задачи останутся в проекте без исполнителя. Сообщи команде, если их нужно передать."
          }
          challenge={confirm === "delete" ? "УДАЛИТЬ" : undefined}
          confirmLabel={confirm === "delete" ? "Удалить проект" : "Покинуть"}
          onClose={() => setConfirm("")}
          onConfirm={async () => {
            if (confirm === "delete") await client.deleteProject(projectId);
            else await client.leaveProject(projectId);
            ui.notify(confirm === "delete" ? "Проект удалён" : "Ты покинул проект");
            router.push("/projects");
          }}
        />
      )}
    </div>
  );
}
