import { Suspense } from "react";
import { LoginView } from "@/features/auth/LoginView";
import { LoadingState } from "@/components/ui";
export default function Page() {
  return (
    <Suspense fallback={<LoadingState />}>
      <LoginView />
    </Suspense>
  );
}
