import type { QueryClient } from "@tanstack/react-query";

/**
 * Keeps every view of server data consistent. Any successful write marks all cached
 * API data stale, so on-screen queries refetch now and the rest refetch when shown.
 * Other open tabs of the app are told to do the same.
 */
let client: QueryClient | null = null;
let channel: BroadcastChannel | null = null;

function refresh() {
  void client?.invalidateQueries({ queryKey: ["api"] });
}

export function registerQueryClient(queryClient: QueryClient) {
  client = queryClient;
  if (!channel && typeof BroadcastChannel !== "undefined") {
    channel = new BroadcastChannel("backit-data");
    channel.onmessage = refresh;
  }
}

export function dataChanged() {
  refresh();
  channel?.postMessage("changed");
}
