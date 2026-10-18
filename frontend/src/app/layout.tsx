import type { Metadata } from "next";
import { DataProvider } from "@/providers/DataProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Сипи — проекты и задачи", template: "%s · Сипи" },
  description: "Задачи, участники и материалы учебных проектов.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" data-scroll-behavior="smooth">
      <body>
        <DataProvider>{children}</DataProvider>
      </body>
    </html>
  );
}
