export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
    public requestId?: string,
  ) {
    super(message);
  }
}

type Options = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string | null;
  idempotencyKey?: string;
  cache?: RequestCache;
  next?: { revalidate?: number };
};

export async function api<T>(path: string, { method = "GET", body, token, idempotencyKey, cache, next }: Options = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      cache,
      next,
    });
  } catch {
    throw new ApiError(0, "network_error", "Can't reach the BackIt API. Check that it is running and try again.");
  }

  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = data?.error;
    if (err) throw new ApiError(res.status, err.code, err.message, err.details ?? {}, err.request_id);
    const detail = Array.isArray(data?.detail) ? data.detail.map((d: { msg: string }) => d.msg).join(", ") : undefined;
    throw new ApiError(res.status, "http_error", detail ?? `Request failed (${res.status}).`);
  }
  return data as T;
}

export function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong. Try again.";
}
