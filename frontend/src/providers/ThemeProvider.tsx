"use client";

import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState } from "react";

export type ThemePreference = "light" | "dark" | "system";

type ThemeContextValue = {
  theme: ThemePreference;
  setTheme: (theme: ThemePreference) => void;
  resolvedTheme: "light" | "dark";
};

const ThemeContext = createContext<ThemeContextValue>({
  theme: "system",
  setTheme: () => {},
  resolvedTheme: "light",
});

const STORAGE_KEY = "sipi-theme";
const mediaQuery = "(prefers-color-scheme: dark)";

function getResolvedTheme(theme: ThemePreference): "light" | "dark" {
  if (theme !== "system") return theme;
  return window.matchMedia(mediaQuery).matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemePreference>("system");
  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">("light");

  useLayoutEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "light" || stored === "dark" || stored === "system") {
        setThemeState(stored);
        setResolvedTheme(getResolvedTheme(stored));
      } else {
        setResolvedTheme(getResolvedTheme("system"));
      }
    } catch {
      setResolvedTheme(getResolvedTheme("system"));
    }
  }, []);

  const setTheme = useCallback((nextTheme: ThemePreference) => {
    setThemeState(nextTheme);
    try {
      localStorage.setItem(STORAGE_KEY, nextTheme);
    } catch {
      // The theme still applies for this session when storage is unavailable.
    }
    const resolved = nextTheme === "system" ? getResolvedTheme("system") : nextTheme;
    setResolvedTheme(resolved);
    document.documentElement.dataset.theme = resolved;
    document.documentElement.style.colorScheme = resolved;
  }, []);

  useEffect(() => {
    const media = window.matchMedia(mediaQuery);
    const syncSystemTheme = () => {
      if (theme === "system") {
        const resolved = media.matches ? "dark" : "light";
        setResolvedTheme(resolved);
        document.documentElement.dataset.theme = resolved;
        document.documentElement.style.colorScheme = resolved;
      }
    };
    media.addEventListener("change", syncSystemTheme);
    const syncStorage = (event: StorageEvent) => {
      if (event.key === STORAGE_KEY && (event.newValue === "light" || event.newValue === "dark" || event.newValue === "system")) {
        setThemeState(event.newValue);
        const resolved = getResolvedTheme(event.newValue);
        setResolvedTheme(resolved);
        document.documentElement.dataset.theme = resolved;
        document.documentElement.style.colorScheme = resolved;
      }
    };
    window.addEventListener("storage", syncStorage);
    return () => {
      media.removeEventListener("change", syncSystemTheme);
      window.removeEventListener("storage", syncStorage);
    };
  }, [theme]);

  const value = useMemo(() => ({ theme, setTheme, resolvedTheme }), [theme, setTheme, resolvedTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
