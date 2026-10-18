import type {
  AssistantReply,
  NotificationItem,
  Invitation,
  Material,
  Project,
  RoleInput,
  AuthChallenge,
  Snapshot,
  Status,
  Task,
  TaskInput,
} from "@/types/domain";

/** Session-authenticated Django API boundary. */
export interface DataClient {
  subscribe(listener: () => void): () => void;
  getSnapshot(): Snapshot | null;
  initialize(): void;
  refresh(): Promise<void>;
  requestCode(username: string, password: string): Promise<AuthChallenge>;
  resendCode(): Promise<AuthChallenge>;
  verifyCode(code: string): Promise<void>;
  register(input: {
    name: string;
    username: string;
    email: string;
    password: string;
    passwordConfirm: string;
  }): Promise<AuthChallenge>;
  logout(): Promise<void>;
  getNotifications(): Promise<{ notifications: NotificationItem[] }>;
  respondNotification(kind: NotificationItem["kind"], id: string, action: "accept" | "decline", role?: RoleInput): Promise<{ notifications: NotificationItem[] }>;
  updateProfile(name: string, bio: string): Promise<void>;
  createTask(input: TaskInput): Promise<Task>;
  updateTask(id: string, input: TaskInput): Promise<void>;
  transitionTask(id: string, status: Status, resultUrl?: string, reason?: string): Promise<void>;
  moveTask(id: string, status: Status, beforeTaskId?: string, reason?: string): Promise<void>;
  deleteTask(id: string): Promise<void>;
  addComment(taskId: string, text: string): Promise<void>;
  createProject(
    name: string,
    description: string,
    role: RoleInput,
    leaderId?: string,
    teacherId?: string,
  ): Promise<Project>;
  deleteProject(id: string): Promise<void>;
  directory(
    query: string,
  ): Promise<Pick<Project, "id" | "name" | "description" | "color" | "symbol">[]>;
  joinProject(id: string, role: RoleInput): Promise<void>;
  leaveProject(id: string): Promise<void>;
  removeMember(projectId: string, userId: string): Promise<void>;
  invite(projectId: string, email: string): Promise<Invitation>;
  cancelInvitation(id: string): Promise<void>;
  acceptInvitation(id: string, role: RoleInput): Promise<void>;
  saveMaterial(
    projectId: string,
    input: Pick<Material, "title" | "description" | "url">,
    id?: string,
  ): Promise<void>;
  deleteMaterial(id: string): Promise<void>;
  updateColumn(projectId: string, id: Status, name: string, limit: number): Promise<void>;
  askAssistant(message: string, projectId?: string): Promise<AssistantReply>;
}
