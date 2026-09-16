import { useUiStore } from "./store";

// Base URL of the FastAPI backend. In docker-compose this is injected as
// NEXT_PUBLIC_API_BASE_URL; locally it defaults to the dev API port.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function authHeaders(): Record<string, string> {
  // Dev auth: the backend trusts X-Dev-User to impersonate a seeded user.
  // In production this is replaced by a real bearer token.
  const role = useUiStore.getState().role;
  return { "X-Dev-User": role };
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { ...authHeaders() },
    cache: "no-store",
  });
  return handle<T>(res);
}

export async function apiSend<T>(
  path: string,
  method: "POST" | "PUT" | "DELETE",
  body?: unknown
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return handle<T>(res);
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: unknown = null;
    let message = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      detail = data;
      if (data?.detail) message = typeof data.detail === "string" ? data.detail : message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function csvUrl(path: string): string {
  return `${API_BASE}${path}`;
}
