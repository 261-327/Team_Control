"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, EmptyState, FormError, Modal } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import { initialRole, RoleFields } from "@/features/projects/ProjectViews";
import { client } from "@/services/client";
import { dateLabel } from "@/lib/format";
import type { NotificationItem, Task } from "@/types/domain";

export function NotificationsBell({ attention }: { attention: Task[] }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [selected, setSelected] = useState<NotificationItem | null>(null);
  const [role, setRole] = useState(initialRole);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const revision = useRef(0);
  const mounted = useRef(false);
  const mutating = useRef(false);

  const load = useCallback(async () => {
    if (mutating.current) return;
    const current = ++revision.current;
    try {
      const result = await client.getNotifications();
      if (mounted.current && current === revision.current) {
        setItems(result.notifications);
        setLoading(false);
      }
    } catch {
      if (mounted.current && current === revision.current) {
        setError("Не удалось обновить уведомления. Попробуйте ещё раз.");
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void load();
    const refresh = () => { if (document.visibilityState === "visible") void load(); };
    const timer = window.setInterval(refresh, 15000);
    window.addEventListener("focus", refresh);
    window.addEventListener("colleagues-changed", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      mounted.current = false;
      revision.current++;
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("colleagues-changed", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [load]);

  async function respond(item: NotificationItem, action: "accept" | "decline") {
    if (mutating.current) return;
    mutating.current = true;
    revision.current++;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await client.respondNotification(item.kind, item.id, action,
        action === "accept" && item.kind !== "colleague" ? role : undefined);
      if (mounted.current) {
        setItems(result.notifications);
        setSelected(null);
        setNotice(action === "decline" ? "Заявка отклонена." : item.kind === "colleague" ? "Коллега добавлен." : "Вы присоединились к проекту.");
        window.dispatchEvent(new Event("colleagues-changed"));
      }
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : "Не удалось обработать заявку.");
    } finally {
      mutating.current = false;
      revision.current++;
      if (mounted.current) setBusy(false);
    }
  }

  const count = items.length + attention.length;
  return <>
    <button type="button" className="notification-button icon-button" aria-label={`Уведомления: ${count}`} aria-haspopup="dialog"
      onClick={() => { setOpen(true); setError(""); void load(); }}>
      <Icon name="bell" size={20} />{count > 0 && <span className="notification-badge">{count > 99 ? "99+" : count}</span>}
    </button>
    {open && <Modal title={selected ? "Принять приглашение" : "Уведомления"}
      description={selected ? selected.title : "Заявки, приглашения и важные задачи"}
      onClose={() => { setOpen(false); setSelected(null); }} busy={busy} sheet>
      <FormError error={error} />
      {notice && <p className="notification-notice" role="status">{notice}</p>}
      {selected ? <form onSubmit={(event) => { event.preventDefault(); void respond(selected, "accept"); }}>
        <RoleFields value={role} onChange={setRole} />
        <p className="form-note">Выберите свою роль именно в этом проекте.</p>
        <div className="form-actions"><Button type="button" variant="secondary" disabled={busy} onClick={() => setSelected(null)}>Назад</Button>
        <Button loading={busy}>Принять и вступить</Button></div>
      </form> : <>
        {loading && <p className="muted">Загрузка уведомлений…</p>}
        {items.map((item) => <article className="notification-request" key={`${item.kind}:${item.id}`}>
          <div className="notification-request-heading"><span className="notification-icon lilac"><Icon name={item.kind === "colleague" ? "users" : "projects"} size={18} /></span>
          <div><strong>{item.title}</strong><p>{item.description}</p></div></div>
          <div className="notification-request-actions">
            <Button disabled={busy} onClick={() => {
              if (item.kind === "colleague") void respond(item, "accept");
              else { setSelected(item); setRole({ ...initialRole }); setError(""); setNotice(""); }
            }}>Принять</Button>
            <Button variant="secondary" disabled={busy} onClick={() => void respond(item, "decline")}>Отклонить</Button>
          </div>
        </article>)}
        {attention.map((task) => <Link className="notification-item" href={`/projects/${task.projectId}/tasks/${task.id}`} key={task.id} onClick={() => setOpen(false)}>
          <span className={`notification-icon ${task.status === "in_review" ? "lilac" : "peach"}`}><Icon name={task.status === "in_review" ? "review" : "clock"} /></span>
          <div><strong>{task.title}</strong><p>{task.status === "in_review" ? "Ожидает твоей проверки" : `Срок прошёл · ${dateLabel(task.deadlineAt)}`}</p></div>
          <Icon name="chevron" size={17} />
        </Link>)}
        {!loading && !count && !error && <EmptyState icon="checkCircle" title="Нет новых уведомлений" description="Здесь появятся заявки в коллеги, приглашения в проекты и важные задачи." />}
        {error && <Button type="button" variant="ghost" disabled={busy} onClick={() => { setError(""); void load(); }}>Обновить</Button>}
      </>}
    </Modal>}
  </>;
}
