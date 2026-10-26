import type { Metadata } from "next";
import localFont from "next/font/local";
import { DataProvider } from "@/providers/DataProvider";
import "./globals.css";
import "./workspace.css";

const workspaceFont = localFont({
  src: "./fonts/Manrope.ttf",
  variable: "--font-workspace",
  display: "swap",
  weight: "200 800",
});

export const metadata: Metadata = {
  title: { default: "Сипи — проекты и задачи", template: "%s · Сипи" },
  description: "Задачи, участники и материалы учебных проектов.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={workspaceFont.variable} data-scroll-behavior="smooth">
      <body>
        <DataProvider>{children}</DataProvider>
      </body>
    </html>
  );
}
