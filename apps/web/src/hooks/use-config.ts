"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import type { PublicConfig } from "@/lib/api/types";

let promise: Promise<PublicConfig> | null = null;

export function useConfig() {
  const [config, setConfig] = useState<PublicConfig | null>(null);
  useEffect(() => {
    promise ??= api<PublicConfig>("/config").catch((e) => {
      promise = null;
      throw e;
    });
    promise.then(setConfig).catch(() => {});
  }, []);
  return config;
}
