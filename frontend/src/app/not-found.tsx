import Link from "next/link";
import { Logo } from "@/components/ui";
export default function NotFound() {
  return (
    <main className="not-found">
      <Logo />
      <span>404</span>
      <h1>Страница не найдена</h1>
      <p>Проверь адрес или перейди к своим задачам.</p>
      <Link className="btn btn-primary" href="/my-tasks">
        К моим задачам →
      </Link>
    </main>
  );
}
