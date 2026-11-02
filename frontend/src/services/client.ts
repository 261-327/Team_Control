import type { DataClient } from "./contracts";
import type {
  AuthChallenge,
  Database,
  Invitation,
  Project,
  RoleInput,
  Snapshot,
  Status,
  Task,
  TaskInput,
  Material,
  AssistantMode,
  AssistantDraft,
  AssistantTurn,
  AssistantHistory,
  NotificationItem,
} from "@/types/domain";

const empty = (): Snapshot => ({
  version: 1,
  now: new Date().toISOString(),
  sessionId: null,
  users: [],
  projects: [],
  memberships: [],
  tasks: [],
  events: [],
  comments: [],
  materials: [],
  invitations: [],
  connectionError: "",
});
class HttpClient implements DataClient {
  private snapshot: Snapshot | null = null;
  private listeners = new Set<() => void>();
  private started = false;
  private revision = 0;
  private authRevision = 0;
  private mutations: Promise<void> = Promise.resolve();
  private refreshing: Promise<void> | null = null;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  getSnapshot = () => this.snapshot;
  private publish(data: Database & { authChallenge?: AuthChallenge | null }) {
    if (this.snapshot && this.snapshot.sessionId !== data.sessionId) this.authRevision++;
    this.snapshot = { ...data, connectionError: "" };
    this.listeners.forEach((listener) => listener());
  }
  private async request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
    try {
      const csrf = document.cookie
        .split("; ")
        .find((item) => item.startsWith("csrftoken="))
        ?.split("=")
        .slice(1)
        .join("=");
      const [route, query] = path.split("?");
      const response = await fetch(`/api/${route}${query ? `?${query}` : ""}`, {
        method,
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
          ...(csrf ? { "X-CSRFToken": decodeURIComponent(csrf) } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(35000),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        if (response.status === 401) {
          this.revision++;
          this.publish(empty());
        }
        throw new Error(data?.error?.message || "Не удалось выполнить запрос. Попробуйте ещё раз.");
      }
      return data as T;
    } catch (error) {
      if (
        error instanceof TypeError ||
        (error instanceof DOMException && ["TimeoutError", "AbortError"].includes(error.name))
      )
        throw new Error(
          "Не удалось связаться с сервером. Проверьте подключение и попробуйте ещё раз.",
        );
      throw error;
    }
  }
  initialize = () => {
    if (!this.started) {
      this.started = true;
      void this.refresh();
    }
  };
  refresh = (): Promise<void> => {
    if (this.refreshing) return this.refreshing;
    const revision = this.revision;
    this.refreshing = this.request<Database & { authChallenge?: AuthChallenge }>("bootstrap")
      .then((data) => {
        if (revision === this.revision) this.publish(data);
      })
      .catch((error: Error) => {
        if (revision !== this.revision) return;
        this.snapshot = { ...(this.snapshot || empty()), connectionError: error.message };
        this.listeners.forEach((listener) => listener());
      })
      .finally(() => {
        this.refreshing = null;
      });
    return this.refreshing;
  };
  private mutate<T extends object = Record<string, never>>(
    path: string,
    method = "POST",
    input?: unknown,
  ): Promise<T> {
    const authRevision = this.authRevision;
    const pending = this.mutations.then(async () => {
      if (authRevision !== this.authRevision)
        throw new Error("Сессия изменилась. Открой форму заново.");
      this.revision++;
      const result = await this.request<T & { snapshot: Database }>(path, method, input);
      this.revision++;
      if (authRevision === this.authRevision) this.publish(result.snapshot);
      return result;
    });
    this.mutations = pending.then(
      () => undefined,
      () => undefined,
    );
    return pending;
  }
  requestCode = (username: string, password: string) =>
    this.request<AuthChallenge>("auth/login", "POST", { username, password });
  resendCode = () => this.request<AuthChallenge>("auth/resend", "POST", {});
  requestPasswordReset = (email: string) =>
    this.request<{ message: string }>("auth/password-reset", "POST", { email });
  confirmPasswordReset = (input: { uid: string; token: string; password: string; passwordConfirm: string }) =>
    this.request<{ message: string }>("auth/password-reset/confirm", "POST", input);
  register = (input: {
    name: string;
    username: string;
    email: string;
    password: string;
    passwordConfirm: string;
  }) => this.request<AuthChallenge>("auth/register", "POST", input);
  verifyCode = async (code: string) => {
    this.revision++;
    this.authRevision++;
    const data = await this.request<Database>("auth/verify", "POST", { code });
    this.revision++;
    this.publish(data);
  };
  logout = async () => {
    this.revision++;
    this.authRevision++;
    const data = await this.request<Database>("auth/logout", "POST", {});
    this.revision++;
    this.publish(data);
  };
  getNotifications = () => this.request<{ notifications: NotificationItem[] }>("notifications");
  respondNotification = (
    kind: NotificationItem["kind"],
    id: string,
    action: "accept" | "decline",
    role?: RoleInput,
  ) =>
    this.mutate<{ notifications: NotificationItem[] }>(
      `notifications/${kind}/${id}/respond`,
      "POST",
      { action, role },
    );
  updateProfile = async (name: string, bio: string) => {
    await this.mutate("profile", "PATCH", { name, bio });
  };
  createTask = async (input: TaskInput) =>
    (await this.mutate<{ task: Task }>("tasks", "POST", input)).task;
  updateTask = async (id: string, input: TaskInput) => {
    await this.mutate(`tasks/${id}`, "PATCH", input);
  };
  transitionTask = async (id: string, status: Status, resultUrl?: string, reason?: string) => {
    await this.mutate(`tasks/${id}/move`, "POST", { status, resultUrl, reason });
  };
  moveTask = async (id: string, status: Status, beforeTaskId?: string, reason?: string) => {
    await this.mutate(`tasks/${id}/move`, "POST", { status, beforeTaskId, reason });
  };
  deleteTask = async (id: string) => {
    await this.mutate(`tasks/${id}`, "DELETE");
  };
  addComment = async (taskId: string, text: string) => {
    await this.mutate(`tasks/${taskId}/comments`, "POST", { text });
  };
  createProject = async (
    name: string,
    description: string,
    role: RoleInput,
    leaderId?: string,
    teacherId?: string,
  ) =>
    (
      await this.mutate<{ project: Project }>("projects", "POST", {
        name,
        description,
        role,
        leaderId,
        teacherId,
      })
    ).project;
  deleteProject = async (id: string) => {
    await this.mutate(`projects/${id}`, "DELETE");
  };
  directory = async (query: string) =>
    (await this.request<{ projects: Project[] }>(`directory?q=${encodeURIComponent(query)}`))
      .projects;
  joinProject = async (id: string, role: RoleInput) => {
    await this.mutate(`projects/${id}/join`, "POST", { role });
  };
  leaveProject = async (id: string) => {
    await this.mutate(`projects/${id}/leave`, "POST", {});
  };
  removeMember = async (projectId: string, userId: string) => {
    await this.mutate(`projects/${projectId}/members/${userId}`, "DELETE");
  };
  invite = async (projectId: string, email: string) =>
    (
      await this.mutate<{ invitation: Invitation }>(`projects/${projectId}/invitations`, "POST", {
        email,
      })
    ).invitation;
  cancelInvitation = async (id: string) => {
    await this.mutate(`invitations/${id}`, "DELETE");
  };
  acceptInvitation = async (id: string, role: RoleInput) => {
    await this.mutate(`invitations/${id}`, "POST", { role });
  };
  saveMaterial = async (
    projectId: string,
    input: Pick<Material, "title" | "description" | "url">,
    id?: string,
  ) => {
    await this.mutate(
      id ? `materials/${id}` : `projects/${projectId}/materials`,
      id ? "PATCH" : "POST",
      input,
    );
  };
  deleteMaterial = async (id: string) => {
    await this.mutate(`materials/${id}`, "DELETE");
  };
  updateColumn = async (projectId: string, id: Status, name: string, limit: number) => {
    await this.mutate(`projects/${projectId}/columns/${id}`, "PATCH", { name, limit });
  };
  assistantHistory = (projectId?: string) =>
    this.request<AssistantHistory>(
      `assistant${projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""}`,
    );
  clearAssistantHistory = async (projectId?: string) => {
    await this.request(
      `assistant${projectId ? `?projectId=${encodeURIComponent(projectId)}` : ""}`,
      "DELETE",
    );
  };
  askAssistant = async (
    message: string,
    mode: AssistantMode,
    requestId: string,
    projectId?: string,
  ) =>
    (
      await this.request<{ turn: AssistantTurn }>("assistant", "POST", {
        message,
        projectId,
        mode,
        requestId,
      })
    ).turn;
  assistantTurn = async (id: string) => {
    const authRevision = this.authRevision;
    const revision = this.revision;
    const result = await this.request<{ turn: AssistantTurn; snapshot?: Database }>(
      `assistant/turns/${id}`,
    );
    if (result.snapshot && authRevision === this.authRevision && revision === this.revision) {
      this.revision++;
      this.publish(result.snapshot);
    }
    return result.turn;
  };
  cancelAssistantTurn = async (id: string) =>
    (await this.request<{ turn: AssistantTurn }>(`assistant/turns/${id}`, "DELETE")).turn;
  confirmAssistantTasks = async (id: string, tasks: AssistantDraft[]) =>
    (await this.mutate<{ turn: AssistantTurn }>(`assistant/turns/${id}/confirm`, "POST", { tasks }))
      .turn;
}
export const client: DataClient = new HttpClient();
