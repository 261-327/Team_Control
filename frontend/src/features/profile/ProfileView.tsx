"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useReadyData } from "@/providers/DataProvider";
import { useUi } from "@/providers/UiContext";
import { client } from "@/services/client";
import { Avatar, Button, Field, FormError, useAction } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";

export function ProfileView() {
  const data = useReadyData();
  const user = data.users.find((u) => u.id === data.sessionId)!;
  const [name, setName] = useState(user.name);
  const [bio, setBio] = useState(user.bio);
  const action = useAction();
  const logoutAction = useAction();
  const ui = useUi();
  const router = useRouter();
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>
            Мой профиль<span className="heading-dot">.</span>
          </h1>
          <p>Имя, почта и роли в проектах.</p>
        </div>
      </div>
      <div className="profile-grid">
        <section className="panel profile-summary">
          <div className="profile-cover">
            <span>✳</span>
            <i />
          </div>
          <Avatar user={user} size="lg" />
          <h2>{user.name}</h2>
          <p>{user.email}</p>
          <span className="role-badge role-member">
            {user.kind === "teacher"
              ? "Преподаватель"
              : user.kind === "staff"
                ? "Координатор"
                : "Студент"}
          </span>
          <div className="profile-stat">
            <div>
              <strong>{data.projects.length}</strong>
              <span>проекта</span>
            </div>
            <div>
              <strong>{data.tasks.filter((t) => t.assigneeId === user.id).length}</strong>
              <span>задач</span>
            </div>
          </div>
          <Button
            variant="ghost"
            loading={logoutAction.busy}
            onClick={() =>
              void logoutAction.run(
                () => client.logout(),
                () => router.push("/login"),
              )
            }
          >
            <Icon name="logout" size={17} />
            Выйти из аккаунта
          </Button>
          <FormError error={logoutAction.error} />
        </section>
        <section className="panel profile-form">
          <h2>Личная информация</h2>
          <p className="muted">Так тебя видят участники твоих проектов.</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void action.run(
                () => client.updateProfile(name, bio),
                () => ui.notify("Профиль обновлён"),
              );
            }}
          >
            <Field label="Имя и фамилия" required>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={100}
                required
              />
            </Field>
            <Field label="Электронная почта" hint="Чтобы изменить почту, обратись к администратору">
              <input type="email" value={user.email} readOnly />
            </Field>
            <Field label="О себе" hint={`${bio.length}/500 символов`}>
              <textarea
                rows={5}
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                maxLength={500}
                placeholder="Чем увлекаешься? Что любишь делать в команде?"
              />
            </Field>
            <FormError error={action.error} />
            <div className="form-actions">
              <Button loading={action.busy}>
                <Icon name="check" size={17} />
                Сохранить изменения
              </Button>
            </div>
          </form>
          <div className="profile-project-roles">
            <h3>Твои роли в проектах</h3>
            {data.memberships
              .filter((m) => m.userId === user.id)
              .map((m) => (
                <Link key={m.projectId} href={`/projects/${m.projectId}`}>
                  <span
                    className={`project-dot ${data.projects.find((p) => p.id === m.projectId)?.color}`}
                  />
                  <strong>{data.projects.find((p) => p.id === m.projectId)?.name}</strong>
                  <span>
                    {m.role === "leader"
                      ? "Руководитель"
                      : m.role === "teacher"
                        ? "Преподаватель"
                        : "Участник"}
                  </span>
                  <Icon name="chevron" size={15} />
                </Link>
              ))}
            {!data.memberships.some((m) => m.userId === user.id) && (
              <p className="muted">Здесь появятся роли после присоединения к проекту.</p>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
