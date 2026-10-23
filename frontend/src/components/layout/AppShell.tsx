"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useData } from "@/providers/DataProvider";
import { UiContext } from "@/providers/UiContext";
import { client } from "@/services/client";
import { canManage, canOverview } from "@/lib/permissions";
import { Avatar, Button, EmptyState, IconButton, LoadingState, Logo, Modal } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import { TaskForm } from "@/features/tasks/TaskForm";
const AssistantPanel = dynamic(() =>
  import("@/features/assistant/AssistantPanel").then((module) => module.AssistantPanel),
);
import type { Task } from "@/types/domain";
import { urgency } from "@/lib/format";

import { NotificationsBell } from "./NotificationsBell";

export function AppShell({ children }: { children: React.ReactNode }) {
  const data = useData();
  const router = useRouter();
  const pathname = usePathname();
  const [mobile, setMobile] = useState(false);
  const [search, setSearch] = useState(false);
  const [query, setQuery] = useState("");
  const [help, setHelp] = useState(false);
  const [assistant, setAssistant] = useState<{ message?: string } | null>(null);
  const [taskForm, setTaskForm] = useState<{
    projectId?: string;
    task?: Task;
  } | null>(null);
  const [toast, setToast] = useState("");
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (data && !data.sessionId && !data.connectionError)
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [data, pathname, router]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearch((open) => !open);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);
  useEffect(
    () => () => {
      if (toastTimer.current) clearTimeout(toastTimer.current);
    },
    [],
  );
  useEffect(() => {
    const sidebar = sidebarRef.current;
    if (!sidebar) return;
    const media = window.matchMedia("(max-width: 960px)");
    const previous = document.activeElement as HTMLElement | null;
    const sync = () => {
      sidebar.inert = media.matches && !mobile;
      if (!media.matches) setMobile(false);
    };
    sync();
    media.addEventListener("change", sync);
    if (mobile && media.matches) sidebar.querySelector<HTMLElement>("a,button")?.focus();
    const keyboard = (event: KeyboardEvent) => {
      if (!mobile || !media.matches) return;
      if (event.key === "Escape") {
        event.preventDefault();
        setMobile(false);
      }
      if (event.key === "Tab") {
        const elements = Array.from(
          sidebar.querySelectorAll<HTMLElement>("a[href],button:not([disabled])"),
        );
        const first = elements[0];
        const last = elements[elements.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", keyboard);
    return () => {
      media.removeEventListener("change", sync);
      document.removeEventListener("keydown", keyboard);
      if (mobile) previous?.focus();
    };
  }, [mobile, data?.sessionId]);
  if (data?.connectionError && !data.sessionId)
    return (
      <div className="page-content">
        <EmptyState
          icon="alert"
          title="Не удалось загрузить пространство"
          description={data.connectionError}
          action={<Button onClick={() => void client.refresh()}>Попробовать снова</Button>}
        />
      </div>
    );
  if (!data || !data.sessionId) return <LoadingState />;
  const user = data.users.find((u) => u.id === data.sessionId)!;
  const currentProjectId = pathname.match(/^\/projects\/([^/]+)/)?.[1];
  const project = data.projects.find((p) => p.id === currentProjectId);
  const nav = [
    { href: "/my-tasks", label: "Мои задачи", icon: "tasks" },
    { href: "/projects", label: "Мои проекты", icon: "projects" },
    { href: "/calendar", label: "Календарь", icon: "calendar" },
    ...(canOverview(data) ? [{ href: "/overview", label: "Обзор команд", icon: "chart" }] : []),
  ];
  const pageTitle =
    project?.name ||
    ({
      "/my-tasks": "Мои задачи",
      "/projects": "Мои проекты",
      "/calendar": "Календарь",
      "/overview": "Обзор команд",
      "/profile": "Мой профиль",
      "/projects/search": "Поиск проектов",
      "/projects/new": "Новый проект",
    }[pathname] ??
      "Рабочее пространство");
  const mine = data.tasks.filter((t) => t.assigneeId === user.id && t.status !== "done");
  const attention = data.tasks.filter(
    (t) =>
      (t.assigneeId === user.id && urgency(t, data.now) === "overdue") ||
      (t.status === "in_review" && canManage(data, t.projectId)),
  );
  const notify = (message: string) => {
    setToast(message);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 4500);
  };
  const closeNav = () => setMobile(false);
  return (
    <UiContext.Provider
      value={{
        notify,
        openTask: (projectId, task) => setTaskForm({ projectId, task }),
        openAssistant: (message) => setAssistant({ message }),
      }}
    >
      <div className="app-shell">
        <a className="skip-link" href="#main-content">
          Перейти к содержимому
        </a>
        {mobile && (
          <button className="sidebar-backdrop" aria-label="Закрыть меню" onClick={closeNav} />
        )}
        <aside
          ref={sidebarRef}
          id="sipi-sidebar"
          className={`sidebar ${mobile ? "is-open" : ""}`}
          aria-label="Главная навигация"
          role={mobile ? "dialog" : undefined}
          aria-modal={mobile || undefined}
        >
          <div className="sidebar-brand">
            <Link href="/my-tasks" onClick={closeNav} aria-label="Сипи — главная">
              <Logo />
            </Link>
            <IconButton
              icon="close"
              label="Закрыть меню"
              className="mobile-close"
              onClick={closeNav}
            />
          </div>
          <div className="workspace-chip">
            <span className="university-mark">
              М<span>П</span>
            </span>
            <div>
              <strong>Московский Политех</strong>
              <span>Проектная деятельность</span>
            </div>
          </div>
          <span className="nav-caption">Пространство</span>
          <nav>
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={closeNav}
                className={`nav-item ${pathname === item.href || (item.href === "/projects" && pathname.startsWith("/projects/")) ? "active" : ""}`}
                aria-current={pathname === item.href ? "page" : undefined}
              >
                <Icon name={item.icon} size={19} />
                <span>{item.label}</span>
                {item.href === "/my-tasks" && mine.length > 0 && (
                  <span className="nav-count">{mine.length}</span>
                )}
              </Link>
            ))}
          </nav>
          <button
            className="sidebar-assistant-entry"
            onClick={() => {
              closeNav();
              setAssistant({});
            }}
          >
            <span>
              <Icon name="sparkles" size={18} />
            </span>
            <div>
              <strong>Сипи AI</strong>
              <small>Помощник по проектам</small>
            </div>
            <Icon name="arrow" size={16} />
          </button>
          <div className="sidebar-project-title">
            <span className="nav-caption">Проекты</span>
            <Link href="/projects/new" title="Создать проект" aria-label="Создать проект">
              <Icon name="plus" size={16} />
            </Link>
          </div>
          <nav className="project-nav">
            {data.projects.slice(0, 5).map((p) => (
              <Link
                key={p.id}
                href={`/projects/${p.id}`}
                onClick={closeNav}
                className={`nav-item ${project?.id === p.id ? "selected" : ""}`}
              >
                <span className={`project-dot ${p.color}`} />
                <span>{p.name.split(" — ")[0]}</span>
              </Link>
            ))}
            {!data.projects.length && <p className="sidebar-empty">Здесь появятся твои проекты</p>}
          </nav>
          <div className="sidebar-bottom">
            <button className="nav-item" onClick={() => setHelp(true)}>
              <Icon name="help" size={19} />
              <span>Помощь и о проекте</span>
              <Icon name="upRight" size={14} />
            </button>
            <Link href="/profile" className="sidebar-profile" onClick={closeNav}>
              <Avatar user={user} />
              <div>
                <strong>{user.name}</strong>
                <span>
                  {user.kind === "teacher"
                    ? "Преподаватель"
                    : user.kind === "staff"
                      ? "Координатор"
                      : "Студент"}
                </span>
              </div>
              <Icon name="down" size={15} />
            </Link>
          </div>
        </aside>
        <div className="workspace-main" inert={mobile}>
          <header className="topbar">
            <div className="breadcrumbs">
              <IconButton
                icon="menu"
                label="Открыть меню"
                aria-expanded={mobile}
                aria-controls="sipi-sidebar"
                className="mobile-menu"
                onClick={() => setMobile(true)}
              />
              <span className="breadcrumb-home">
                <Icon name="home" size={16} />
              </span>
              <Icon name="chevron" size={13} />
              {project ? (
                <>
                  <Link href="/projects">Проекты</Link>
                  <Icon name="chevron" size={13} />
                </>
              ) : null}
              <span>{pageTitle}</span>
            </div>
            <div className="topbar-actions">
              <button
                className="search-trigger"
                aria-label="Поиск по пространству"
                aria-keyshortcuts="Meta+K Control+K"
                onClick={() => setSearch(true)}
              >
                <Icon name="search" size={17} />
                <span>Поиск по пространству</span>
                <kbd>⌘ K</kbd>
              </button>
              <NotificationsBell key={data.sessionId} attention={attention} />
              <Link className="topbar-avatar" href="/profile" aria-label="Открыть профиль">
                <Avatar user={user} />
              </Link>
            </div>
          </header>
          {data.connectionError && (
            <div className="storage-warning" role="status">
              <Icon name="alert" size={16} />
              <span>{data.connectionError} Показана последняя загруженная версия.</span>
              <button onClick={() => void client.refresh()}>Обновить</button>
            </div>
          )}
          <main
            id="main-content"
            className="page-content"
            tabIndex={-1}
            key={`${data.sessionId}:${pathname}`}
          >
            {children}
          </main>
        </div>
        {!assistant && (
          <button
            className="assistant-launcher"
            onClick={() => setAssistant({})}
            aria-label="Открыть ИИ-помощника"
          >
            <span>
              <Icon name="sparkles" size={23} />
            </span>
            <strong>Сипи AI</strong>
            <span className="assistant-launcher-label">Помощник</span>
          </button>
        )}
        {toast && (
          <div className="toast" role="status">
            <Icon name="checkCircle" size={20} />
            {toast}
            <IconButton icon="close" label="Закрыть уведомление" onClick={() => setToast("")} />
          </div>
        )}
      </div>
      {taskForm && (
        <TaskForm
          {...taskForm}
          onClose={() => setTaskForm(null)}
          onSaved={() => {
            setTaskForm(null);
            notify(taskForm.task ? "Изменения сохранены" : "Задача создана");
          }}
        />
      )}
      {assistant && (
        <AssistantPanel
          key={data.sessionId}
          projectId={project?.id}
          initialMessage={assistant.message}
          onClose={() => setAssistant(null)}
        />
      )}
      {search && (
        <Modal
          title="Найти в пространстве"
          description="Проекты и задачи, к которым у тебя есть доступ"
          onClose={() => setSearch(false)}
        >
          <div className="search-field">
            <Icon name="search" />
            <input
              autoFocus
              aria-label="Поиск проектов и задач"
              placeholder="Название задачи или проекта…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div className="search-results">
            {!query.trim() ? (
              <p className="muted">Начни вводить название</p>
            ) : (
              <>
                {data.projects
                  .filter((p) => p.name.toLowerCase().includes(query.toLowerCase()))
                  .map((p) => (
                    <Link
                      href={`/projects/${p.id}`}
                      key={p.id}
                      onClick={() => {
                        setSearch(false);
                        setQuery("");
                      }}
                    >
                      <span className={`project-icon ${p.color}`}>
                        <Icon name={p.symbol} />
                      </span>
                      <div>
                        <strong>{p.name}</strong>
                        <span>Проект</span>
                      </div>
                      <Icon name="arrow" size={17} />
                    </Link>
                  ))}
                {data.tasks
                  .filter((t) => t.title.toLowerCase().includes(query.toLowerCase()))
                  .map((t) => (
                    <Link
                      href={`/projects/${t.projectId}/tasks/${t.id}`}
                      key={t.id}
                      onClick={() => {
                        setSearch(false);
                        setQuery("");
                      }}
                    >
                      <Icon name="tasks" />
                      <div>
                        <strong>{t.title}</strong>
                        <span>{data.projects.find((p) => p.id === t.projectId)?.name}</span>
                      </div>
                      <Icon name="arrow" size={17} />
                    </Link>
                  ))}
                {!data.projects.some((p) => p.name.toLowerCase().includes(query.toLowerCase())) &&
                  !data.tasks.some((t) => t.title.toLowerCase().includes(query.toLowerCase())) && (
                    <EmptyState
                      icon="search"
                      title="Ничего не нашлось"
                      description="Попробуй другое название."
                    />
                  )}
              </>
            )}
          </div>
        </Modal>
      )}
      {help && (
        <Modal
          title="О Сипи"
          description="Сервис для проектной деятельности"
          onClose={() => setHelp(false)}
        >
          <div className="help-content">
            <Logo />
            <p>
              Сипи помогает вести задачи проекта, работать с командой и хранить ссылки на материалы.
            </p>
            <div>
              <Icon name="tasks" />
              <span>
                <strong>Мои задачи</strong>
                <p>Назначенные тебе задачи и ближайшие сроки.</p>
              </span>
            </div>
            <div>
              <Icon name="projects" />
              <span>
                <strong>Проекты</strong>
                <p>Переключай доску и список, обсуждай задачи и делись ссылками.</p>
              </span>
            </div>
            <div>
              <Icon name="sparkles" />
              <span>
                <strong>Помощник</strong>
                <p>Здесь можно посмотреть ближайшие сроки. ИИ-агент будет подключён позже.</p>
              </span>
            </div>
            <p className="field-hint">
              Поиск по задачам: ⌘K / Ctrl+K. Закрыть панель или форму: Escape. Вопросы команде — в{" "}
              <a
                href="https://github.com/261-327/Team_Control/issues"
                target="_blank"
                rel="noreferrer"
              >
                GitHub проекта
              </a>
              .
            </p>
          </div>
        </Modal>
      )}
    </UiContext.Provider>
  );
}
