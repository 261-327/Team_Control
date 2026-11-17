"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Field, FormError, useAction } from "@/components/ui";
import { client } from "@/services/client";

export function EmailChangeForm() {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [challenge, setChallenge] = useState<{ expiresAt: string; resendAt: string } | null>(null);
  const action = useAction();
  const router = useRouter();
  if (!open)
    return (
      <Button type="button" variant="secondary" onClick={() => setOpen(true)}>
        Изменить почту
      </Button>
    );
  return (
    <section aria-label="Изменение почты">
      <h3>Изменить почту</h3>
      <p className="muted">
        До подтверждения действует прежний адрес. После смены потребуется войти заново на всех
        устройствах.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void action.run(async () => {
            if (challenge) {
              await client.confirmEmailChange(code);
              setCode("");
              router.push("/login");
            } else {
              const result = await client.requestEmailChange(email, password);
              setPassword("");
              setChallenge(result);
            }
          });
        }}
      >
        {challenge ? (
          <>
            <p role="status">Проверь новый почтовый ящик. Код действует 5 минут.</p>
            <Field label="Код подтверждения новой почты" required>
              <input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                maxLength={6}
                required
              />
            </Field>
            <p className="muted">
              Повторный запрос доступен после {new Date(challenge.resendAt).toLocaleTimeString()}.
              Для нового кода снова введи пароль.
            </p>
            <Button
              type="button"
              variant="secondary"
              disabled={action.busy}
              onClick={() => {
                setChallenge(null);
                setCode("");
              }}
            >
              Запросить новый код
            </Button>
          </>
        ) : (
          <>
            <Field label="Новая электронная почта" required>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                maxLength={254}
                required
              />
            </Field>
            <Field label="Текущий пароль" required>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                maxLength={4096}
                required
              />
            </Field>
          </>
        )}
        <FormError error={action.error} />
        <div className="form-actions">
          <Button
            type="button"
            variant="secondary"
            disabled={action.busy}
            onClick={() => {
              setOpen(false);
              setPassword("");
              setCode("");
              setChallenge(null);
            }}
          >
            Закрыть
          </Button>
          <Button loading={action.busy}>
            {challenge ? "Подтвердить новую почту" : "Получить код"}
          </Button>
        </div>
      </form>
    </section>
  );
}
