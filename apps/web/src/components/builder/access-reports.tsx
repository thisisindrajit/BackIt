"use client";

import { useState } from "react";
import { FlagIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { authedApi, useApi } from "@/hooks/use-api";
import { useAction } from "@/hooks/use-action";
import { shortDate } from "@/lib/format";
import type { BuilderAccessReport } from "@/lib/api/types";
import { ConfirmDialog } from "./confirm-dialog";

const statusLabel = { open: "Open", resolved: "Fixed", refunded: "Refunded" } as const;

export function AccessReports({ productId }: { productId: string }) {
  const { data, reload } = useApi<BuilderAccessReport[]>(`/products/${productId}/access-reports`);
  const { pending, run } = useAction();
  const [open, setOpen] = useState<string | null>(null);
  const [note, setNote] = useState("");

  if (!data?.length) return null;
  const openCount = data.filter((r) => r.status === "open").length;

  async function reply(id: string) {
    const ok = await run("reply", () => authedApi(`/access-reports/${id}/reply`, { method: "POST", body: { note: note.trim() } }), "Reply sent");
    if (ok) {
      setOpen(null);
      setNote("");
      await reload();
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <h3 className="flex items-center gap-2 text-sm font-medium">
        <FlagIcon className="size-4" aria-hidden />
        Access reports
        {openCount ? <Badge variant="destructive">{openCount} open</Badge> : null}
      </h3>
      {openCount ? (
        <p className="text-sm text-muted-foreground">Referral payouts are paused until every open report is fixed or refunded.</p>
      ) : null}
      <ul className="flex flex-col divide-y rounded-lg border text-sm">
        {data.map((r) => (
          <li key={r.id} className="flex flex-col gap-2 px-3 py-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex min-w-0 flex-col gap-1">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{r.backer_name}</span>
                {r.badge_number ? <span className="tabular text-muted-foreground">No. {r.badge_number}</span> : null}
                <Badge variant={r.status === "open" ? "outline" : "secondary"}>{statusLabel[r.status]}</Badge>
              </span>
              <p className="text-pretty">“{r.message}”</p>
              <p className="text-xs text-muted-foreground">
                {r.backer_email} · Reported {shortDate(r.created_at)} ·{" "}
                {r.code_redeemed_at ? `Code redeemed ${shortDate(r.code_redeemed_at)}` : "Code not redeemed"}
              </p>
              {r.builder_note ? <p className="text-muted-foreground">You replied: {r.builder_note}</p> : null}
            </div>
            {r.status === "open" ? (
              <ConfirmDialog
                open={open === r.id}
                onOpenChange={(v) => {
                  setOpen(v ? r.id : null);
                  setNote(v ? (r.builder_note ?? "") : "");
                }}
                trigger={<Button variant="outline" size="sm" className="shrink-0">{r.builder_note ? "Edit reply" : "Reply"}</Button>}
                title={`Reply to ${r.backer_name}`}
                description="They get your reply by email. Payouts resume when they mark it fixed, or when you refund them from the table below."
                confirmLabel="Send reply"
                pending={pending === "reply"}
                disabled={note.trim().length < 2}
                onConfirm={() => reply(r.id)}
              >
                <Field>
                  <FieldLabel htmlFor={`reply-${r.id}`}>Your reply</FieldLabel>
                  <Textarea id={`reply-${r.id}`} value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} />
                </Field>
              </ConfirmDialog>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
