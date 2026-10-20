import "server-only";
import { notFound } from "next/navigation";
import { api, ApiError } from "./client";
import type { LedgerPage, PublicCampaign } from "./types";

export async function getPublicCampaign(slug: string, ref?: string) {
  const q = ref ? `?ref=${encodeURIComponent(ref)}` : "";
  try {
    return await api<PublicCampaign>(`/public/campaigns/${encodeURIComponent(slug)}${q}`, { cache: "no-store" });
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}

export async function getLedger(slug: string, cursor?: string) {
  const q = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return api<LedgerPage>(`/public/campaigns/${encodeURIComponent(slug)}/ledger${q}`, { cache: "no-store" });
}
