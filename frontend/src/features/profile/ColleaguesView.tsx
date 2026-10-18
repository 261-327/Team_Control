"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Field, FormError, Modal } from "@/components/ui";

type Colleague = {
  id: number;
  userId: number;
  username: string;
  name: string;
  bio: string;
  state: "accepted" | "incoming" | "outgoing";
  projectIds: number[];
};
type ProjectOption = { id: number; name: string };
type Result = { colleagues: Colleague[]; projects: ProjectOption[]; message?: string };

async function request(path: string, body?: object, signal?: AbortSignal): Promise<Result> {
  const token = document.cookie.split("; ").find((value) => value.startsWith("csrftoken="))?.slice(10);
  const response = await fetch(`/api/colleagues/${path}`, {
    method: body ? "POST" : "GET",
    credentials: "same-origin",
    cache: "no-store",
    signal,
    headers: {
      Accept: "application/json",
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { "X-CSRFToken": decodeURIComponent(token) } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error?.message || "Не удалось загрузить коллег.");
  return result as Result;
}

export function ColleaguesView() {
  const [rows, setRows] = useState<Colleague[]>([]);
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [inviting, setInviting] = useState<Colleague | null>(null);
  const [projectId, setProjectId] = useState("");
  const [inviteError, setInviteError] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Colleague | null>(null);
  const [removing, setRemoving] = useState<Colleague | null>(null);
  const revision = useRef(0);
  const mutating = useRef(false);

  useEffect(() => {
    const closeMenus = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      document.querySelectorAll<HTMLDetailsElement>(".profile-colleague-menu[open]").forEach((menu) => {
        if (event instanceof KeyboardEvent || !menu.contains(event.target as Node)) menu.open = false;
      });
    };
    document.addEventListener("click", closeMenus);
    document.addEventListener("keydown", closeMenus);
    return () => {
      document.removeEventListener("click", closeMenus);
      document.removeEventListener("keydown", closeMenus);
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      if (mutating.current) return;
      const current = ++revision.current;
      try {
        const result = await request("", undefined, controller.signal);
        if (!controller.signal.aborted && current === revision.current) {
          setRows(result.colleagues);
          setProjects(result.projects);
          setError("");
        }
      } catch {
        if (!controller.signal.aborted && current === revision.current) setError("Не удалось обновить список коллег.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    const refresh = () => { if (document.visibilityState === "visible") void load(); };
    const timer = window.setInterval(refresh, 30000);
    window.addEventListener("focus", refresh);
    window.addEventListener("colleagues-changed", refresh);
    return () => {
      controller.abort();
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("colleagues-changed", refresh);
    };
  }, []);

  async function mutate(path: string, body: object) {
    if (mutating.current) return;
    mutating.current = true;
    revision.current++;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await request(path, body);
      setRows(result.colleagues);
          setProjects(result.projects);
      setMessage(result.message || "Сохранено.");
      window.dispatchEvent(new Event("colleagues-changed"));
      setRemoving(null);
      setInviting(null);
      if (!path) setUsername("");
    } catch (cause) {
      const failure = cause instanceof Error ? cause.message : "Не удалось выполнить действие.";
      if (path.endsWith("/invite/")) setInviteError(failure);
      else setError(failure);
    } finally { mutating.current = false; revision.current++; setBusy(false); }
  }

  const colleagues = rows.filter((row) => row.state === "accepted");
  const incoming = rows.filter((row) => row.state === "incoming");
  const outgoing = rows.filter((row) => row.state === "outgoing");
  const person = (row: Colleague) => (
    <span className="profile-colleague-person">
      <strong>{row.name}</strong><span className="muted">@{row.username}</span>
    </span>
  );
  const eligibleProjects = projects.filter((project) => !inviting?.projectIds.includes(project.id));


  return (
    <section className="panel profile-colleagues" aria-labelledby="colleagues-title">
      <div className="profile-colleagues-heading"><h2 id="colleagues-title">Коллеги</h2><span className="profile-colleagues-count">{colleagues.length}</span></div>
      <details className="profile-colleague-add">
        <summary><span aria-hidden="true">＋</span> Добавить коллегу</summary>
        <form onSubmit={(event) => { event.preventDefault(); void mutate("", { username }); }} style={{ marginTop: 16 }}>
          <Field label="Никнейм коллеги" required>
            <input value={username} onChange={(event) => setUsername(event.target.value)} maxLength={150} placeholder="Никнейм или @никнейм" required />
          </Field>
          <Button loading={busy} className="profile-colleague-submit">Отправить заявку</Button>
        </form>
      </details>
      <FormError error={error} />
      {message && <p role="status">{message}</p>}
      {loading && <p className="muted">Загружаем коллег…</p>}
      {incoming.length > 0 && <h3>Входящие заявки</h3>}
      {incoming.map((row) => <div key={row.id} className="profile-colleague-row profile-colleague-pending">
        {person(row)}<div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button loading={busy} onClick={() => void mutate(`${row.id}/respond/`, { action: "accept" })}>Принять</Button>
          <Button variant="ghost" disabled={busy} onClick={() => void mutate(`${row.id}/respond/`, { action: "decline" })}>Отклонить</Button>
        </div>
      </div>)}
      {outgoing.length > 0 && <h3>Отправленные заявки</h3>}
      {outgoing.map((row) => <div key={row.id} className="profile-colleague-row profile-colleague-pending">
        {person(row)}<Button variant="ghost" disabled={busy} onClick={() => void mutate(`${row.id}/respond/`, { action: "cancel" })}>Отменить заявку</Button>
      </div>)}
      
      {colleagues.map((row) => <div key={row.id} className="profile-colleague-row">
        <button type="button" onClick={() => setSelected(row)} className="profile-colleague-profile">
          <span aria-hidden="true" className="profile-colleague-avatar">{row.username.slice(0, 1).toUpperCase()}</span>{person(row)}
        </button>
        <details className="profile-colleague-menu"><summary aria-label={`Действия с коллегой ${row.username}`}>⋯</summary>
          <div className="profile-colleague-menu-panel">
            <button type="button" disabled={busy} onClick={(event) => {
              event.currentTarget.closest("details")?.removeAttribute("open");
              setInviteError(""); setInviting(row);
              setProjectId(String(projects.find((project) => !row.projectIds.includes(project.id))?.id || ""));
            }}>Пригласить в проект</button>
            <button type="button" className="profile-colleague-remove" disabled={busy} onClick={(event) => {
              event.currentTarget.closest("details")?.removeAttribute("open"); setRemoving(row);
            }}>Удалить из коллег</button>
          </div>
        </details>
      </div>)}
      {!loading && !colleagues.length && <p className="muted">Добавьте коллегу по никнейму. После принятия заявки он появится здесь.</p>}
      {inviting && <Modal title="Пригласить в проект" description={`Коллега @${inviting.username}`} onClose={() => setInviting(null)} busy={busy}>
        <form onSubmit={(event) => { event.preventDefault(); setInviteError(""); void mutate(`${inviting.id}/invite/`, { projectId }); }}>
          {eligibleProjects.length > 0 ? <>
            <Field label="Ваш проект" required><select value={projectId} onChange={(event) => setProjectId(event.target.value)} required>
              <option value="">Выберите проект</option>
              {eligibleProjects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select></Field>
            <p className="form-note">Коллега получит приглашение в аккаунте и выберет роль при вступлении.</p>
          </> : <p className="muted">Нет доступных проектов: создайте свой проект или выберите коллегу, который ещё не вступил в него.</p>}
          <FormError error={inviteError} />
          <div className="form-actions"><Button type="button" variant="secondary" disabled={busy} onClick={() => setInviting(null)}>Отмена</Button>
          <Button loading={busy} disabled={!projectId || !eligibleProjects.length}>Пригласить</Button></div>
        </form>
      </Modal>}
      {selected && <Modal title={selected.name} onClose={() => setSelected(null)}>
        <p>@{selected.username}</p><h3>О себе</h3><p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{selected.bio || "Информация пока не добавлена."}</p>
      </Modal>}
      {removing && <Modal title="Удалить коллегу?" onClose={() => setRemoving(null)} busy={busy}>
        <p>Удалить @{removing.username} из списка коллег?</p>
        <Button loading={busy} onClick={() => void mutate(`${removing.id}/respond/`, { action: "remove" })}>Удалить</Button>
        <Button variant="ghost" disabled={busy} onClick={() => setRemoving(null)}>Отмена</Button>
        <FormError error={error} />
      </Modal>}
    </section>
  );
}
