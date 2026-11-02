"use client";

import { useCallback } from "react";
import { queryOptions, useQuery, useQueryClient } from "@tanstack/react-query";
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

export const apiKey = (path: string) => ["api", path] as const;

export function apiQuery<T>(path: string) {
  return queryOptions({ queryKey: apiKey(path), queryFn: () => authedApi<T>(path) });
}

export function useApi<T>(path: string | null) {
  const queryClient = useQueryClient();
  const query = useQuery({ ...apiQuery<T>(path ?? ""), enabled: Boolean(path) });

  const reload = useCallback(async () => {
    if (path) await queryClient.invalidateQueries({ queryKey: apiKey(path) });
  }, [queryClient, path]);

  const setData = useCallback((value: T) => {
    if (path) queryClient.setQueryData(apiKey(path), value);
  }, [queryClient, path]);

  return {
    data: query.data ?? null,
    setData,
    error: query.error,
    loading: query.isPending && Boolean(path),
    fetching: query.isFetching,
    reload,
  };
}

/** Marks cached API data stale and refetches whatever is on screen. */
export function useInvalidate() {
  const queryClient = useQueryClient();
  return useCallback(
    (...paths: string[]) => Promise.all(paths.map((p) => queryClient.invalidateQueries({ queryKey: apiKey(p) }))),
    [queryClient],
  );
}

/** Warms the cache before navigation so the next page renders with data. */
export function usePrefetch() {
  const queryClient = useQueryClient();
  return useCallback((...paths: string[]) => {
    for (const p of paths) void queryClient.prefetchQuery(apiQuery(p));
  }, [queryClient]);
}
