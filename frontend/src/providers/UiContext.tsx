"use client";
import { createContext, useContext } from "react";
import type { Task } from "@/types/domain";

type Ui = {
  notify: (message: string) => void;
  openTask: (projectId?: string, task?: Task) => void;
  openAssistant: (message?: string) => void;
};
export const UiContext = createContext<Ui>({
  notify: () => {},
  openTask: () => {},
  openAssistant: () => {},
});
export function useUi() {
  return useContext(UiContext);
}
