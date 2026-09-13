import { funFactFor } from "@/lessons/funFacts";

/* A short, always-there bottom banner - a different color from the rest of
   the page on purpose, so it reads as "aside" rather than "instruction."
   Deterministic content (see lessons/funFacts.ts), so it never depends on
   a live model being connected or within quota. */
export function FunFactBanner({ issueType }: { issueType: string }) {
  return (
    <div className="mt-8 rounded-md border border-points/30 bg-points/10 px-4 py-3 text-sm text-ink">
      {funFactFor(issueType)}
    </div>
  );
}
