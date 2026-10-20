import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const tone: Record<string, "done" | "wait" | "bad" | "neutral"> = {
  verified: "done", active: "done", revoked: "bad", completed: "done", delivered: "done", paid: "done", success: "done", connected: "done", published: "done", payable: "done",
  created: "wait", pending: "wait", pending_provider: "wait", held: "wait", reserved: "wait", submitted: "wait", queued: "wait", processing: "wait", open: "wait", draft: "wait", unclaimed: "wait",
  failed: "bad", dead: "bad", refunded: "bad", reversed: "bad", blocked: "bad", returned: "bad", stale: "bad", expired: "bad", cancelled: "bad", partial: "bad",
};

const label: Record<string, string> = {
  pending_provider: "Awaiting PayPal",
  not_configured: "No webhook",
  not_connected: "Not connected",
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const t = tone[status] ?? "neutral";
  return (
    <Badge
      variant="outline"
      className={cn(
        "capitalize",
        t === "done" && "border-transparent bg-secondary text-secondary-foreground",
        t === "wait" && "border-transparent bg-accent text-accent-foreground",
        t === "bad" && "border-transparent bg-destructive/10 text-destructive",
        className,
      )}
    >
      {label[status] ?? status.replace(/_/g, " ")}
    </Badge>
  );
}
