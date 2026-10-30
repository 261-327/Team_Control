"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useData } from "@/providers/DataProvider";
import { client } from "@/services/client";
import { Button, Field, FormError, LoadingState, Logo, useAction } from "@/components/ui";
import { Icon } from "@/components/ui/Icon";
import type { AuthChallenge, Snapshot } from "@/types/domain";
function safeNext(value: string | null) {
  return value &&
    /^\/(my-tasks|projects|invitations|calendar|overview|profile)(\/|\?|$)/.test(value) &&
    !value.includes("\\")
    ? value
    : "/my-tasks";
}
export function LoginView({ register = false }: { register?: boolean }) {
  const data = useData();
  if (!data) return <LoadingState />;
  return <LoginForm register={register} data={data} />;
}
function LoginForm({ register, data }: { register: boolean; data: Snapshot }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNext(searchParams.get("next"));
  const action = useAction();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [challenge, setChallenge] = useState<AuthChallenge | null>(data.authChallenge || null);
  const [tick, setTick] = useState(() => Date.now());
  useEffect(() => {
    if (data?.sessionId) router.replace(next);
  }, [data, next, router]);
  useEffect(() => {
    if (!challenge) return;
    const timer = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [challenge]);
  if (!data) return <LoadingState />;
  const resendSeconds = challenge ? Math.max(0, Math.ceil((challenge.resendAt - tick) / 1000)) : 0;
  const expiresSeconds = challenge
    ? Math.max(0, Math.ceil((challenge.expiresAt - tick) / 1000))
    : 0;
  return (
    <div className="auth-page">
      <aside className="auth-story">
        <Link href="/">
          <Logo />
        </Link>
        <div className="auth-story-copy">
          <h1>
            Проекты.
            <br />
            Задачи.
            <br />
            <em>Команда.</em>
          </h1>
          <p>Рабочее пространство для проектной деятельности в университете.</p>
          <div className="auth-product-preview" aria-hidden="true">
            <div className="auth-preview-heading">
              <Icon name="projects" size={18} />
              <strong>Проект на семестр</strong>
              <span>•••</span>
            </div>
            <div className="auth-preview-tabs">
              <span>Задачи</span>
              <span>Команда</span>
              <span>Материалы</span>
            </div>
            <div className="auth-preview-board">
              <div>
                <span>
                  <i />К выполнению
                </span>
                <article>
                  Изучить требования<small>Аналитика</small>
                </article>
              </div>
              <div>
                <span>
                  <i />В работе
                </span>
                <article>
                  Собрать прототип<small>Дизайн</small>
                </article>
              </div>
              <div>
                <span>
                  <i />
                  Готово
                </span>
                <article>
                  Описать сценарии<small>Команда</small>
                </article>
              </div>
            </div>
          </div>
        </div>
        <div className="auth-story-footer">
          <span>Московский Политех · Проектная деятельность</span>
          <span>2026</span>
        </div>
      </aside>
      <main className="auth-main">
        <div className="auth-mobile-logo">
          <Logo />
        </div>
        <div className="auth-form">
          <h2>{challenge ? "Код подтверждения" : register ? "Создать аккаунт" : "Вход в Сипи"}</h2>
          <p>
            {challenge ? (
              <>
                Отправили код на <strong>{challenge.email}</strong>.
              </>
            ) : register ? (
              "Заполни данные, чтобы начать работу с командой."
            ) : (
              "Введи логин или почту и пароль."
            )}
          </p>
          {data.connectionError && (
            <div role="alert">
              <FormError error={data.connectionError} />
              <Button variant="secondary" onClick={() => void client.refresh()}>
                Повторить подключение
              </Button>
            </div>
          )}
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (challenge)
                void action.run(
                  () => client.verifyCode(code),
                  () => router.push(next),
                );
              else
                void action.run(
                  () =>
                    register
                      ? client.register({ name, username, email, password, passwordConfirm })
                      : client.requestCode(username, password),
                  (result) => {
                    setChallenge(result);
                    setTick(Date.now());
                    setPassword("");
                    setPasswordConfirm("");
                  },
                );
            }}
          >
            {challenge ? (
              <>
                {challenge.delivery === "console" && (
                  <p className="form-note">
                    Локальный запуск: письмо с кодом выведено в терминал Django.
                  </p>
                )}
                <Field
                  label="Шестизначный код"
                  hint={
                    expiresSeconds > 0
                      ? `Код действует ещё ${Math.floor(expiresSeconds / 60)}:${String(expiresSeconds % 60).padStart(2, "0")}`
                      : "Срок кода истёк. Запроси новый."
                  }
                  required
                >
                  <input
                    autoFocus
                    className="otp-input"
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="[0-9]{6}"
                    maxLength={6}
                    placeholder="000000"
                    required
                  />
                </Field>
              </>
            ) : (
              <>
                {register && (
                  <Field label="Имя и фамилия" required>
                    <input
                      autoFocus
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      maxLength={100}
                      autoComplete="name"
                      required
                    />
                  </Field>
                )}
                <Field label={register ? "Логин" : "Логин или почта"} required>
                  <input
                    autoFocus={!register}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    maxLength={register ? 150 : 254}
                    autoComplete="username"
                    autoCapitalize="none"
                    required
                  />
                </Field>
                {register && (
                  <Field label="Электронная почта" hint="На неё придёт код подтверждения" required>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      autoComplete="email"
                      maxLength={254}
                      required
                    />
                  </Field>
                )}
                <Field
                  label="Пароль"
                  hint={
                    register
                      ? "Не меньше 8 символов. Не используй слишком простой пароль."
                      : undefined
                  }
                  required
                >
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={register ? "new-password" : "current-password"}
                    maxLength={4096}
                    minLength={register ? 8 : undefined}
                    required
                  />
                </Field>
                {!register && (
                  <p className="auth-switch" style={{ textAlign: "right" }}>
                    <Link href="/forgot-password">Забыли пароль?</Link>
                  </p>
                )}
                {register && (
                  <Field label="Повтори пароль" required>
                    <input
                      type="password"
                      value={passwordConfirm}
                      onChange={(e) => setPasswordConfirm(e.target.value)}
                      autoComplete="new-password"
                      minLength={8}
                      maxLength={4096}
                      required
                    />
                  </Field>
                )}
              </>
            )}
            <FormError error={action.error} />
            <Button className="auth-submit" loading={action.busy} disabled={!!data.connectionError}>
              {challenge ? "Подтвердить и войти" : register ? "Создать аккаунт" : "Продолжить"}
              <Icon name="arrow" size={18} />
            </Button>
          </form>
          {challenge ? (
            <div className="auth-code-actions">
              <button
                disabled={resendSeconds > 0 || action.busy}
                onClick={() =>
                  void action.run(
                    () => client.resendCode(),
                    (result) => {
                      setChallenge(result);
                      setTick(Date.now());
                      setCode("");
                    },
                  )
                }
              >
                {resendSeconds > 0 ? `Новый код через ${resendSeconds} с` : "Отправить код ещё раз"}
              </button>
              <button
                disabled={action.busy}
                onClick={() => {
                  setChallenge(null);
                  setCode("");
                  action.setError("");
                }}
              >
                Вернуться к входу
              </button>
            </div>
          ) : (
            <p className="auth-switch">
              {register ? "Уже есть аккаунт?" : "Впервые здесь?"}{" "}
              <Link href={`${register ? "/login" : "/register"}?next=${encodeURIComponent(next)}`}>
                {register ? "Войти" : "Создать аккаунт"}
                <Icon name="arrow" size={14} />
              </Link>
            </p>
          )}
        </div>
        <footer className="auth-footer">
          <Icon name="lock" size={13} />
          Вход с подтверждением по почте
        </footer>
      </main>
    </div>
  );
}
