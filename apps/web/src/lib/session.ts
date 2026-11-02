import "server-only";
import { cache } from "react";
import { headers } from "next/headers";
import { connection } from "next/server";

export const getSession = cache(async () => {
  // Prefetches can resolve headers, but auth initialization must wait for a real request.
  await connection();
  const requestHeaders = await headers();
  const { auth } = await import("./auth");
  return auth.api.getSession({ headers: requestHeaders });
});
