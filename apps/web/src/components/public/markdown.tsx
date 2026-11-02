import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

function omitNode<P extends { node?: unknown }>(props: P): Omit<P, "node"> {
  const rest = { ...props };
  delete rest.node;
  return rest;
}

const components: Components = {
  h1: (p) => <h2 className="mt-4 text-3xl leading-tight first:mt-0" {...omitNode(p)} />,
  h2: (p) => <h2 className="mt-4 text-3xl leading-tight first:mt-0" {...omitNode(p)} />,
  h3: (p) => <h3 className="mt-2 font-sans text-lg font-medium first:mt-0" {...omitNode(p)} />,
  h4: (p) => <h4 className="font-sans text-base font-medium" {...omitNode(p)} />,
  p: (p) => <p className="text-pretty" {...omitNode(p)} />,
  a: (p) => <a className="text-link underline underline-offset-4" target="_blank" rel="noopener noreferrer nofollow" {...omitNode(p)} />,
  ul: (p) => <ul className="flex list-disc flex-col gap-2 pl-6 marker:text-primary" {...omitNode(p)} />,
  ol: (p) => <ol className="flex list-decimal flex-col gap-2 pl-6 marker:text-muted-foreground" {...omitNode(p)} />,
  li: (p) => <li className="pl-1" {...omitNode(p)} />,
  blockquote: (p) => <blockquote className="border-l-2 border-primary pl-5 text-foreground/75 italic" {...omitNode(p)} />,
  hr: () => <hr className="border-foreground/10" />,
  code: (p) => <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.85em]" {...omitNode(p)} />,
  pre: (p) => <pre className="overflow-x-auto rounded-2xl bg-muted p-4 text-sm [&_code]:bg-transparent [&_code]:p-0" {...omitNode(p)} />,
  table: (p) => (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse font-sans text-base" {...omitNode(p)} />
    </div>
  ),
  th: (p) => <th className="border-b border-foreground/10 py-2 pr-4 text-left font-medium" {...omitNode(p)} />,
  td: (p) => <td className="border-b border-foreground/5 py-2 pr-4" {...omitNode(p)} />,
  img: () => null,
};

export function MarkdownStory({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-5", className)}>
      <Markdown remarkPlugins={[remarkGfm]} components={components} skipHtml>
        {children}
      </Markdown>
    </div>
  );
}
