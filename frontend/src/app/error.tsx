"use client";
import { Button, EmptyState } from "@/components/ui";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="not-found">
      <EmptyState
        icon="alert"
        title="Не удалось открыть страницу"
        description="Попробуй открыть страницу ещё раз. Сохранённые изменения останутся на сервере."
        action={<Button onClick={reset}>Попробовать снова</Button>}
      />
    </main>
  );
}
