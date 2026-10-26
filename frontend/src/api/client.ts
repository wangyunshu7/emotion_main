const BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";
let csrf = "";
export const setCSRF = (value: string) => {
  csrf = value;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(BASE + path, {
    method,
    credentials: "include",
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(method === "GET" ? {} : { "X-CSRF-Token": csrf }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => ({}))) as {
      error?: { code?: string; message?: string };
    };
    if (response.status === 401 && !path.startsWith("/auth/"))
      window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(
      response.status,
      error.error?.code || "NETWORK_ERROR",
      error.error?.message || "请求未完成，请稍后重试",
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function downloadExport() {
  const data = await api<unknown>("/me/export");
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "心晴日记导出.json";
  link.click();
  URL.revokeObjectURL(url);
}

export function message(error: unknown) {
  return error instanceof Error ? error.message : "操作未完成，请重试";
}

export function clearPrivateStorage() {
  for (let i = sessionStorage.length - 1; i >= 0; i--) {
    const key = sessionStorage.key(i);
    if (key?.startsWith("emotion-draft:")) sessionStorage.removeItem(key);
  }
}
