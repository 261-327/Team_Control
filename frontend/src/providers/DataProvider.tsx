"use client";

import { createContext, useContext, useEffect, useSyncExternalStore } from "react";
import { client } from "@/services/client";
import type { Snapshot } from "@/types/domain";

const Context = createContext<Snapshot | null>(null);
const serverSnapshot = () => null;
export function DataProvider({ children }: { children: React.ReactNode }) {
  const snapshot = useSyncExternalStore(client.subscribe, client.getSnapshot, serverSnapshot);
  useEffect(() => {
    client.initialize();
    const refresh = () => {
      if (document.visibilityState === "visible") void client.refresh();
    };
    const timer = setInterval(refresh, 30000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, []);
  return <Context.Provider value={snapshot}>{children}</Context.Provider>;
}
export function useData() {
  return useContext(Context);
}
export function useReadyData() {
  const data = useData();
  if (!data) throw new Error("DataProvider is not ready");
  return data;
}
