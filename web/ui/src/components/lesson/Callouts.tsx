import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/* Top-of-panel callouts: what this column is, a pointer toward fixing it,
   and a nudge - written by the LLM in real time when one is connected
   (see web/chat.py:callouts), grounded in the level's real facts either
   way. This is the "what can I even do here" answer, so it has to load
   before the learner needs it, not after they've already given up. */
export function Callouts({ levelId }: { levelId: number }) {
  const [lines, setLines] = useState<string[] | null>(null);
  const [grounded, setGrounded] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLines(null);
    api
      .callouts(levelId)
      .then((res) => {
        if (cancelled) return;
        setLines(res.callouts);
        setGrounded(res.grounded);
      })
      .catch(() => {
        if (!cancelled) setLines([]);
      });
    return () => {
      cancelled = true;
    };
  }, [levelId]);

  if (lines === null) {
    return (
      <div className="flex gap-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-14 flex-1 animate-pulse rounded-md border border-line bg-surface" />
        ))}
      </div>
    );
  }
  if (lines.length === 0) return null;

  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
          What you can do here
        </span>
        {grounded === false && <span className="text-[10px] text-fail">not personalized live yet</span>}
      </div>
      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
        {lines.map((line, i) => (
          <div
            key={i}
            className="rounded-md border border-line bg-surface px-3 py-2 text-xs leading-snug text-ink"
          >
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}
