import { cn } from "@/lib/utils";

/** A labelled settings-style row: copy on the left, fields on the right on wide screens. */
export function FormSection({
  title,
  description,
  children,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "grid gap-6 border-t py-8 first:border-t-0 first:pt-0 last:pb-0 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:gap-12",
        className,
      )}
    >
      <div className="flex flex-col gap-1.5">
        <h2 className="text-xl">{title}</h2>
        {description ? <p className="text-sm text-pretty text-muted-foreground">{description}</p> : null}
      </div>
      <div className="flex min-w-0 flex-col gap-6">{children}</div>
    </section>
  );
}

/** Right-aligned action bar under a FormSection stack, lined up with the field column. */
export function FormActions({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid border-t pt-6 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:gap-12">
      <div className="flex flex-wrap items-center gap-3 lg:col-start-2">{children}</div>
    </div>
  );
}
