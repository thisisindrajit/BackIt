"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { PublicConfig } from "@/lib/api/types";

export function useConfig() {
  const { data } = useQuery({ queryKey: ["config"], queryFn: () => api<PublicConfig>("/config"), staleTime: Infinity });
  return data ?? null;
}
