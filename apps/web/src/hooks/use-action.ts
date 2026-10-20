"use client";

import { useState } from "react";
import { toast } from "sonner";
import { errorMessage } from "@/lib/api/client";

export function useAction() {
  const [pending, setPending] = useState<string | null>(null);
  async function run<T>(key: string, fn: () => Promise<T>, success?: string): Promise<T | undefined> {
    setPending(key);
    try {
      const result = await fn();
      if (success) toast.success(success);
      return result;
    } catch (e) {
      toast.error(errorMessage(e));
      return undefined;
    } finally {
      setPending(null);
    }
  }
  return { pending, run };
}
