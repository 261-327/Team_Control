"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { client } from "@/services/client";
import { Button, Field, FormError, Logo } from "@/components/ui";

export function ForgotPasswordView() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await client.requestPasswordReset(email.trim());
      setSent(true);
      setError("");
      // The public message is identical for existing and unknown addresses.
      if (!result.message) setSent(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось отправить запрос. Попробуйте позже.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page" style={{ gridTemplateColumns: "minmax(0, 1fr)", minHeight: "100dvh" }}>
    <main className="auth-main">
      <div className="auth-mobile-logo"><Link href="/login"><Logo /></Link></div>
      <section className="auth-form" aria-labelledby="reset-title">
        <h2 id="reset-title">Восстановление пароля</h2>
        {sent ? (
          <>
            <p role="status">Если аккаунт с такой подтверждённой почтой существует, мы отправили инструкции по восстановлению.</p>
            <p className="auth-switch"><Link href="/login">Вернуться ко входу</Link></p>
          </>
        ) : (
          <>
            <p>Укажи почту, привязанную к аккаунту. Если адрес подтверждён, на него придёт ссылка для смены пароля.</p>
            <form onSubmit={submit}>
              <Field label="Электронная почта" required>
                <input
                  type="email"
                  name="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="email"
                  maxLength={254}
                  autoFocus
                  required
                />
              </Field>
              <FormError error={error} />
              <Button className="auth-submit" loading={busy} disabled={busy}>Отправить ссылку</Button>
            </form>
            <p className="auth-switch"><Link href="/login">Вернуться ко входу</Link></p>
          </>
        )}
      </section>
    </main>
    </div>
  );
}
