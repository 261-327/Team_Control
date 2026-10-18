"use client";
import { useSyncExternalStore } from "react";

const eventName = "sipi-preference";
let memoryPreference: string | null = null;
const subscribe = (callback: () => void) => {
  window.addEventListener(eventName, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(eventName, callback);
    window.removeEventListener("storage", callback);
  };
};
export function useBoardPreference() {
  const value = useSyncExternalStore(
    subscribe,
    () => {
      if (memoryPreference) return memoryPreference;
      try {
        const stored = localStorage.getItem("sipi-board-view");
        return stored === "board" || stored === "list"
          ? stored
          : window.matchMedia("(max-width: 700px)").matches
            ? "list"
            : "board";
      } catch {
        return "list";
      }
    },
    () => "board",
  );
  return [
    value,
    (next: string) => {
      try {
        localStorage.setItem("sipi-board-view", next);
        memoryPreference = null;
      } catch {
        memoryPreference = next;
      }
      window.dispatchEvent(new Event(eventName));
    },
  ] as const;
}
