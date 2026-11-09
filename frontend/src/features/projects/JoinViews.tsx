"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { useUi } from "@/providers/UiContext";
import { client } from "@/services/client";
import { Button, EmptyState, FormError, useAction } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import { initialRole, RoleFields } from "./ProjectViews";
import type { Project } from "@/types/domain";
import { dateLabel } from "@/lib/format";

export function ProjectSearchView() {
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState(false);
  const [results, setResults] = useState<
    Pick<Project, "id" | "name" | "description" | "color" | "symbol">[]
  >([]);
  const action = useAction();
  return (
    <>
      <Link className="back-link" href="/projects">
        <Icon name="back" size={16} />
        Мои проекты
      </Link>
      <div className="page-heading">
        <div>
          <h1>Поиск проектов</h1>
          <p>
            Найди проект среди своих команд. Для вступления в новую команду нужно приглашение
            руководителя.
          </p>
        </div>
      </div>
      <form
        className="directory-search panel"
        onSubmit={(event) => {
          event.preventDefault();
          void action.run(
            () => client.directory(query),
            (rows) => {
              setResults(rows);
              setSearched(true);
            },
          );
        }}
      >
        <div className="search-field">
          <Icon name="search" />
          <input
            aria-label="Название проекта"
            placeholder="Например, робототехника…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            maxLength={255}
          />
        </div>
        <Button loading={action.busy} disabled={!query.trim()}>
          Найти проект
          <Icon name="arrow" size={16} />
        </Button>
      </form>
      <FormError error={action.error} />
      <div className="directory-results">
        {results.map((project) => (
          <article className="panel directory-card" key={project.id}>
            <span className={`project-icon large ${project.color}`}>
              <Icon name={project.symbol} size={28} />
            </span>
            <div>
              <h2>{project.name}</h2>
              <p>{project.description}</p>
            </div>
            <Link className="btn btn-secondary" href={`/projects/${project.id}`}>
              Открыть проект
            </Link>
          </article>
        ))}
      </div>
      {!results.length && (
        <EmptyState
          icon="search"
          title={searched ? "Пока нет совпадений" : "Поиск в своих проектах"}
          description="Приглашения в новые проекты находятся в уведомлениях. Можно также открыть ссылку от руководителя."
        />
      )}
    </>
  );
}

export function InvitationView() {
  const { inviteId } = useParams<{ inviteId: string }>();
  const data = useReadyData();
  const router = useRouter();
  const ui = useUi();
  const action = useAction();
  const [role, setRole] = useState(initialRole);
  const invitation = data.invitations.find((i) => i.id === inviteId);
  const user = data.users.find((u) => u.id === data.sessionId)!;
  if (!invitation || invitation.email !== user.email)
    return (
      <EmptyState
        icon="lock"
        title="Это приглашение для другого аккаунта"
        description="Войди с почтой, на которую руководитель создал приглашение."
        action={
          <Link href="/projects" className="btn btn-secondary">
            К моим проектам
          </Link>
        }
      />
    );
  const expired = Date.parse(invitation.expiresAt) <= Date.parse(data.now);
  if (invitation.status === "cancelled" || expired)
    return (
      <EmptyState
        icon="clock"
        title={expired ? "Срок приглашения истёк" : "Приглашение отменено"}
        description="Попроси руководителя создать новое приглашение."
      />
    );
  return (
    <div className="invitation-page panel">
      <span className="invitation-art">
        <Icon name="users" size={40} />
        <span>✦</span>
      </span>
      <span className="eyebrow">ПРИГЛАШЕНИЕ</span>
      <h1>{invitation.status === "accepted" ? "Приглашение принято" : "Приглашение в проект"}</h1>
      <h2>{invitation.projectName}</h2>
      <p className="muted">
        Приглашает {data.users.find((u) => u.id === invitation.createdBy)?.name}.<br />
        Для {invitation.email} · до {dateLabel(invitation.expiresAt)}
      </p>
      {invitation.status === "accepted" ? (
        <Link href={`/projects/${invitation.projectId}`} className="btn btn-primary">
          Открыть проект
          <Icon name="arrow" size={16} />
        </Link>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(
              () => client.acceptInvitation(inviteId, role),
              () => {
                ui.notify("Ты присоединился к проекту");
                router.push(`/projects/${invitation.projectId}`);
              },
            );
          }}
        >
          <RoleFields value={role} onChange={setRole} />
          <FormError error={action.error} />
          <Button loading={action.busy}>
            Принять приглашение
            <Icon name="arrow" size={17} />
          </Button>
          <p className="field-hint">Приглашение действует только для указанной почты.</p>
        </form>
      )}
    </div>
  );
}
