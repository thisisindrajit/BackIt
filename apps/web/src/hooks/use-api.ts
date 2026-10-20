"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { authClient } from "@/lib/auth-client";
import { api, ApiError } from "@/lib/api/client";

let cached: { token: string; exp: number } | null = null;

async function getToken() {
  const now = Date.now() / 1000;
  if (cached && cached.exp - 60 > now) return cached.token;
  const { data } = await authClient.token();
  if (!data?.token) throw new ApiError(401, "unauthenticated", "Your session has ended. Sign in again.");
  const payload = JSON.parse(atob(data.token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
  cached = { token: data.token, exp: payload.exp };
  return data.token;
}

export function clearTokenCache() {
  cached = null;
}

type CallOptions = Omit<Parameters<typeof api>[1], "token">;

export function authedApi<T>(path: string, options: CallOptions = {}) {
  return getToken().then((token) => api<T>(path, { ...options, token }));
}

export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(Boolean(path));
  const seq = useRef(0);

  const reload = useCallback(async () => {
    if (!path) return;
    const id = ++seq.current;
    setLoading(true);
    try {
      const result = await authedApi<T>(path);
      if (id === seq.current) {
        setData(result);
        setError(null);
      }
    } catch (e) {
      if (id === seq.current) setError(e);
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void reload();
  }, [reload]);

  return { data, setData, error, loading, reload };
}
