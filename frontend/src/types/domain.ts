export type Status = "todo" | "in_progress" | "in_review" | "done" | `column_${number}`;
export type Profession = "developer" | "designer" | "analyst" | "security" | "tester" | "other";
export type User = {
  id: string;
  name: string;
  email: string;
  bio: string;
  color: string;
  kind: "student" | "teacher" | "staff";
  scopeProjectIds?: string[];
};
export type Membership = {
  projectId: string;
  userId: string;
  role: "leader" | "member" | "teacher";
  profession: Profession;
  specialization: string;
  customRole: string;
};
export type Project = {
  id: string;
  name: string;
  description: string;
  color: string;
  symbol: string;
  createdAt: string;
  columns: { id: Status; name: string; limit: number }[];
};
export type Task = {
  position?: number;
  id: string;
  projectId: string;
  title: string;
  description: string;
  assigneeId: string;
  deadlineAt: string;
  status: Status;
  tag: string;
  resultUrl: string;
  createdBy: string;
  createdAt: string;
  submittedAt?: string;
  acceptedAt?: string;
};
export type TaskEvent = {
  id: string;
  taskId: string;
  userId: string;
  text: string;
  createdAt: string;
};
export type Comment = {
  id: string;
  taskId: string;
  userId: string;
  text: string;
  createdAt: string;
};
export type Material = {
  id: string;
  projectId: string;
  title: string;
  description: string;
  url: string;
  createdBy: string;
  createdAt: string;
};
export type Invitation = {
  id: string;
  projectId: string;
  email: string;
  createdBy: string;
  expiresAt: string;
  status: "pending" | "accepted" | "cancelled";
  projectName?: string;
};
export type Database = {
  version: 1;
  now: string;
  sessionId: string | null;
  users: User[];
  projects: Project[];
  memberships: Membership[];
  tasks: Task[];
  events: TaskEvent[];
  comments: Comment[];
  materials: Material[];
  invitations: Invitation[];
};
export type AuthChallenge = {
  email: string;
  mode: "login" | "register";
  expiresAt: number;
  resendAt: number;
  delivery: "console" | "email";
};
export type Snapshot = Database & { connectionError: string; authChallenge?: AuthChallenge | null };
export type TaskInput = Pick<
  Task,
  "projectId" | "title" | "description" | "assigneeId" | "deadlineAt" | "tag"
>;
export type RoleInput = { profession: Profession; specialization: string; customRole: string };
export type AssistantReply = { text: string; taskIds?: string[] };
