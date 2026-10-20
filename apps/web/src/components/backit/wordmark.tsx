import Image from "next/image";
import Link from "next/link";

export function Wordmark({ href = "/" }: { href?: string }) {
  return (
    <Link
      href={href}
      className="group/wordmark inline-flex items-center gap-2 rounded-full text-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <Image
        src="/logo.png"
        alt=""
        width={32}
        height={32}
        priority
        className="size-8 transition-transform duration-300 ease-(--ease-out) group-hover/wordmark:-rotate-6"
      />
      <span className="font-display tracking-tight">
        Back<em className="text-primary-deep">It</em>
      </span>
    </Link>
  );
}
