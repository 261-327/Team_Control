import { ProjectLayout } from "@/features/projects/ProjectViews";
export default function Layout({ children }: { children: React.ReactNode }) {
  return <ProjectLayout>{children}</ProjectLayout>;
}
