"use client";

import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { client } from "@/services/client";
import { Button, Field, FormError, LoadingState, Logo } from "@/components/ui";

function ResetPasswordForm() {
  const params = useSearchParams();
  const uid = params.get("uid") || "";
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await client.confirmPasswordReset({ uid, token, password, passwordConfirm });
      setDone(true);
      setPassword("");
      setPasswordConfirm("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось изменить пароль. Запросите новую ссылку.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-main">
      <div className="auth-mobile-logo"><Link href="/login"><Logo /></Link></div>
      <section className="auth-form" aria-labelledby="reset-title">
        <h2 id="reset-title">Новый пароль</h2>
        {done ? (
          <>
            <p role="status">Пароль изменён. Теперь войдите с новым паролем и подтвердите вход кодом из письма.</p>
            <p className="auth-switch"><Link href="/login">Перейти ко входу</Link></p>
          </>
        ) : !uid || !token ? (
          <>
            <p role="alert">Ссылка неполная или повреждена. Запросите восстановление заново.</p>
            <p className="auth-switch"><Link href="/forgot-password">Запросить новую ссылку</Link></p>
          </>
        ) : (
          <>
            <p>Придумай новый пароль. После смены потребуется войти заново.</p>
            <form onSubmit={submit}>
              <Field label="Новый пароль" hint="Пароль проверяется по правилам безопасности сайта." required>
                <input
                  type="password"
                  name="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  maxLength={4096}
                  autoFocus
                  required
                />
              </Field>
              <Field label="Повтори новый пароль" required>
                <input
                  type="password"
                  name="passwordConfirm"
                  value={passwordConfirm}
                  onChange={(event) => setPasswordConfirm(event.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  maxLength={4096}
                  required
                />
              </Field>
              <FormError error={error} />
              <Button className="auth-submit" loading={busy} disabled={busy}>Сменить пароль</Button>
            </form>
          </>
        )}
      </section>
    </main>
  );
}

export function ResetPasswordView() {
  return <Suspense fallback={<LoadingState />}><ResetPasswordForm /></Suspense>;
}
