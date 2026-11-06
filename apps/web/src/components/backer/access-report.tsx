"use client";

import { useState } from "react";
import { FlagIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmDialog } from "@/components/builder/confirm-dialog";
import { authedApi, useInvalidate } from "@/hooks/use-api";
import { useAction } from "@/hooks/use-action";
import { shortDate } from "@/lib/format";
import type { AccessReport } from "@/lib/api/types";

export function AccessReportPanel({ backingId, productName, report }: { backingId: string; productName: string; report: AccessReport | null }) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const { pending, run } = useAction();
  const invalidate = useInvalidate();

  async function submit() {
    const ok = await run(
      "report",
      () => authedApi(`/backings/${backingId}/access-report`, { method: "POST", body: { message: message.trim() } }),
      "Reported. The builder has been emailed.",
    );
    if (ok) {
      setOpen(false);
      setMessage("");
      await invalidate("/me/backings");
    }
  }

  async function resolve() {
    const ok = await run("resolve", () => authedApi(`/backings/${backingId}/access-report/resolve`, { method: "POST" }), "Marked as fixed");
    if (ok) await invalidate("/me/backings");
  }

  if (report?.status === "open") {
    return (
      <div className="flex flex-col gap-3 rounded-2xl bg-accent px-4 py-3 text-sm text-accent-foreground">
        <p className="flex items-center gap-2 font-medium">
          <FlagIcon className="size-4" aria-hidden />
          You reported an access problem on {shortDate(report.created_at)}
        </p>
        <p className="text-pretty">“{report.message}”</p>
        {report.builder_note ? (
          <p className="text-pretty">
            <span className="font-medium">Builder replied:</span> {report.builder_note}
          </p>
        ) : (
          <p>Waiting for the builder. Referral payouts on this campaign are paused until it’s fixed.</p>
        )}
        <Button size="sm" variant="outline" className="w-fit" onClick={resolve} disabled={pending === "resolve"}>
          It works now
        </Button>
      </div>
    );
  }

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <Button variant="link" size="sm" className="h-auto w-fit p-0 text-muted-foreground">
          Can’t access {productName}? Report it
        </Button>
      }
      title="Report an access problem"
      description="The builder gets an email right away. Referral payouts on this campaign pause until you mark it fixed or you’re refunded."
      confirmLabel="Send report"
      pending={pending === "report"}
      disabled={message.trim().length < 10}
      onConfirm={submit}
    >
      <Field>
        <FieldLabel htmlFor={`report-${backingId}`}>What went wrong?</FieldLabel>
        <Textarea
          id={`report-${backingId}`}
          value={message}
          maxLength={2000}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="The code says it’s invalid when I enter it on the upgrade page."
        />
        <FieldDescription>At least 10 characters.</FieldDescription>
      </Field>
    </ConfirmDialog>
  );
}
