import "server-only";
import { cacheLife, cacheTag } from "next/cache";
import { notFound } from "next/navigation";
import { api, ApiError } from "./client";
import type { LedgerPage, PublicCampaign, PublicCampaignCard } from "./types";

// Public pages are shared by every visitor, so their API reads are cached on the server.
// Seat counts and the ledger move with each sale, so entries refresh within seconds.
async function fetchPublicCampaign(slug: string, ref?: string) {
  "use cache";
  cacheLife("seconds");
  cacheTag(`campaign:${slug}`);
  const q = ref ? `?ref=${encodeURIComponent(ref)}` : "";
  try {
    return { campaign: await api<PublicCampaign>(`/public/campaigns/${encodeURIComponent(slug)}${q}`) };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return { campaign: null };
    throw e;
  }
}

export async function getPublicCampaign(slug: string, ref?: string) {
  const { campaign } = await fetchPublicCampaign(slug, ref);
  if (!campaign) notFound();
  return campaign;
}

export async function getLedger(slug: string, cursor?: string) {
  "use cache";
  cacheLife("seconds");
  cacheTag(`campaign:${slug}`, `ledger:${slug}`);
  const q = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return api<LedgerPage>(`/public/campaigns/${encodeURIComponent(slug)}/ledger${q}`);
}

export type ExploreSort = "trending" | "new";

export async function listPublicCampaigns(sort: ExploreSort) {
  "use cache";
  cacheLife("minutes");
  cacheTag("campaigns");
  return api<PublicCampaignCard[]>(`/public/campaigns?sort=${sort}`);
}
