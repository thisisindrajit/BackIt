/** Headline that rises in word by word. Marketing-only; reduced motion falls back to a fade. */
export function HeroWords({ words, accent }: { words: string[]; accent: string }) {
  const all = [...words, accent];
  return (
    <h1 className="max-w-5xl text-[clamp(3rem,8.5vw,6rem)] leading-[0.95] tracking-[-0.035em]">
      {all.map((w, i) => (
        <span key={i} className="rise inline-block" style={{ animationDelay: `${120 + i * 60}ms`, animationDuration: "700ms" }}>
          {i === all.length - 1 ? <em>{w}</em> : w}
          {i < all.length - 1 ? "\u00a0" : null}
        </span>
      ))}
    </h1>
  );
}
