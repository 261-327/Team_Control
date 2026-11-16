import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { DataProvider } from "@/providers/DataProvider";
import { ThemeProvider } from "@/providers/ThemeProvider";
import "./globals.css";
import "./workspace.css";

const workspaceFont = localFont({
  src: "./fonts/Manrope.ttf",
  variable: "--font-workspace",
  display: "swap",
  weight: "200 800",
});

const themeInitScript = `(function(){try{var t=localStorage.getItem("sipi-theme")||"system";var d=t==="system"? (window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"):t;document.documentElement.dataset.theme=d;document.documentElement.style.colorScheme=d;}catch(e){document.documentElement.dataset.theme="light";}})();`;

export const metadata: Metadata = {
  title: { default: "Сипи — проекты и задачи", template: "%s · Сипи" },
  description: "Задачи, участники и материалы учебных проектов.",
  applicationName: "Сипи",
  appleWebApp: { capable: true, title: "Сипи", statusBarStyle: "default" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#f8f8f8" }, { media: "(prefers-color-scheme: dark)", color: "#171918" }],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className={workspaceFont.variable} data-scroll-behavior="smooth" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <ThemeProvider>
          <DataProvider>{children}</DataProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
