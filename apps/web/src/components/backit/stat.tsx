import { cn } from "@/lib/utils";

export function Stat({ label, value, hint, className }: { label: string; value: React.ReactNode; hint?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <dt className="text-[0.8125rem] text-muted-foreground">{label}</dt>
      <dd className="tabular font-heading text-[1.75rem] leading-tight">{value}</dd>
      {hint ? <dd className="text-xs text-muted-foreground">{hint}</dd> : null}
    </div>
  );
}
