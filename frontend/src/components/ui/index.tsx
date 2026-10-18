"use client";

import { cloneElement, isValidElement, useEffect, useId, useRef, useState } from "react";
import type { ButtonHTMLAttributes, ReactElement, ReactNode } from "react";
import type { User } from "@/types/domain";
import { initials } from "@/lib/format";
import { Icon } from "./Icon";

let openModalCount = 0;
let originalBodyOverflow = "";

export function Button({
  variant = "primary",
  loading,
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
}) {
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={`btn btn-${variant} ${className}`}
      aria-busy={loading || undefined}
    >
      {loading ? <span className="spinner" /> : null}
      {children}
    </button>
  );
}
export function IconButton({
  icon,
  label,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { icon: string; label: string }) {
  return (
    <button
      {...props}
      aria-label={label}
      title={label}
      className={`icon-button ${props.className || ""}`}
    >
      <Icon name={icon} />
    </button>
  );
}
export function Avatar({ user, size = "sm" }: { user?: User; size?: "xs" | "sm" | "md" | "lg" }) {
  return (
    <span
      className={`avatar avatar-${size} ${user?.color || "neutral"}`}
      title={user?.name || "Не назначен"}
    >
      {user ? initials(user.name) : <Icon name="user" size={14} />}
    </span>
  );
}
function SunMark() {
  return (
    <g fill="none" stroke="var(--brand-yellow, #ffb600)" strokeWidth="9" strokeLinecap="round">
      <path d="M63 30a25 25 0 1 0 0 29" strokeLinecap="butt" />
      <path d="m7 31 13 5M19 12l10 11M39 4l4 14" strokeWidth="8" />
    </g>
  );
}
export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`logo ${compact ? "compact" : ""}`}>
      <svg
        className={compact ? "brand-symbol" : "brand-wordmark"}
        viewBox={compact ? "0 0 80 80" : "0 0 253 80"}
        fill="currentColor"
        role="img"
        aria-label="Сипи"
      >
        <SunMark />
        {!compact && (
          <g transform="translate(-12 0)">
            <path d="M84 20h12v33l25-33h12v52h-12V39L96 72H84Z" />
            <path d="M144 20h49v52h-12V32h-25v40h-12Z" />
            <path d="M204 20h12v33l25-33h12v52h-12V39l-25 33h-12Z" />
          </g>
        )}
      </svg>
    </span>
  );
}
export function Modal({
  title,
  description,
  children,
  onClose,
  busy = false,
  wide = false,
  sheet = false,
  focusSelector,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
  wide?: boolean;
  sheet?: boolean;
  focusSelector?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descId = useId();
  useEffect(() => {
    const dialog = ref.current!;
    const trigger = document.activeElement as HTMLElement | null;
    if (openModalCount === 0) originalBodyOverflow = document.body.style.overflow;
    openModalCount += 1;
    document.body.style.overflow = "hidden";
    dialog.showModal();
    // React handles autoFocus before a closed dialog is focusable; focus after showModal.
    const field = dialog.querySelector<HTMLElement>(
      focusSelector || "input:not([type='hidden']),textarea,select",
    );
    field?.focus({ preventScroll: true });
    return () => {
      dialog.close();
      openModalCount -= 1;
      if (openModalCount === 0) document.body.style.overflow = originalBodyOverflow;
      trigger?.focus({ preventScroll: true });
    };
  }, [focusSelector]);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? "modal-wide" : ""} ${sheet ? "sheet" : ""}`}
      aria-labelledby={titleId}
      aria-describedby={description ? descId : undefined}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current && !busy) {
          const bounds = ref.current!.getBoundingClientRect();
          if (
            event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom
          )
            onClose();
        }
      }}
    >
      <div className="modal-header">
        <div>
          <h2 id={titleId}>{title}</h2>
          {description && <p id={descId}>{description}</p>}
        </div>
        <IconButton icon="close" label="Закрыть" onClick={onClose} disabled={busy} />
      </div>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}
export function Field({
  label,
  hint,
  children,
  required,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  required?: boolean;
}) {
  const labelId = useId();
  const hintId = useId();
  const control = isValidElement(children)
    ? cloneElement(
        children as ReactElement<{ "aria-labelledby"?: string; "aria-describedby"?: string }>,
        { "aria-labelledby": labelId, "aria-describedby": hint ? hintId : undefined },
      )
    : children;
  return (
    <label className="field">
      <span className="field-label">
        <span id={labelId}>{label}</span>
        {required && (
          <span className="required" aria-hidden="true">
            {" "}
            *
          </span>
        )}
      </span>
      {control}
      {hint && (
        <span className="field-hint" id={hintId}>
          {hint}
        </span>
      )}
    </label>
  );
}
export function FormError({ error }: { error: string }) {
  return error ? (
    <div className="form-error" role="alert">
      <Icon name="alert" size={17} />
      {error}
    </div>
  ) : null;
}
export function EmptyState({
  title = "Пока ничего нет",
  description,
  action,
  icon = "folder",
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
  icon?: string;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} size={27} />
      </span>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}
export function LoadingState() {
  return (
    <div className="page-loading" role="status">
      <Logo compact />
      <p>Загрузка…</p>
      <span className="loading-track">
        <i />
      </span>
    </div>
  );
}
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const locked = useRef(false);
  async function run<T>(action: () => Promise<T>, success?: (result: T) => void) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await action();
      success?.(result);
      return result;
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Не удалось выполнить действие. Попробуйте ещё раз.",
      );
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  return { busy, error, setError, run };
}
export function ConfirmDialog({
  title,
  description,
  confirmLabel = "Удалить",
  onConfirm,
  onClose,
  challenge,
}: {
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => Promise<unknown>;
  onClose: () => void;
  challenge?: string;
}) {
  const action = useAction();
  const [confirmation, setConfirmation] = useState("");
  return (
    <Modal title={title} description={description} onClose={onClose} busy={action.busy}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!challenge || confirmation === challenge) void action.run(onConfirm, onClose);
        }}
      >
        <span className="confirm-icon">
          <Icon name="trash" size={27} />
        </span>
        {challenge && (
          <Field label={`Для подтверждения введите «${challenge}»`} required>
            <input
              autoFocus
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
              autoComplete="off"
            />
          </Field>
        )}
        <FormError error={action.error} />
        <div className="form-actions">
          <Button type="button" variant="secondary" onClick={onClose} disabled={action.busy}>
            Отмена
          </Button>
          <Button
            variant="danger"
            loading={action.busy}
            disabled={!!challenge && confirmation !== challenge}
          >
            {confirmLabel}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
