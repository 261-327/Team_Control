import { Suspense } from "react";
import { CalendarView } from "@/features/tasks/CalendarView";
export default function Page() {
  return (
    <Suspense>
      <CalendarView />
    </Suspense>
  );
}
