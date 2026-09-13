import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Fade } from "@/components/ui/Fade";
import { Mascot } from "@/components/Mascot";
import type { CodeReveal as CodeRevealT } from "@/lib/api";

/* "Show me the code" - the real lines that just ran (see
   web/code_snippets.py), not a generic tutorial snippet, plus one plain
   sentence explaining what those lines actually do. Used after both a
   level's recap (the fix that was kept) and the modeling recap (the model
   that was chosen) - fetch/resetKey are injected so one component covers
   both. */
export function CodeReveal({
  resetKey,
  heading,
  fetchCode,
  onNext,
  nextLabel = "Continue",
  onLoaded,
}: {
  resetKey: string | number;
  heading: string;
  fetchCode: () => Promise<CodeRevealT>;
  onNext: () => void;
  nextLabel?: string;
  onLoaded?: (data: CodeRevealT) => void;
}) {
  const [data, setData] = useState<CodeRevealT | null>(null);

  useEffect(() => {
    setData(null);
    fetchCode().then((d) => {
      setData(d);
      onLoaded?.(d);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);

  if (!data) {
    return <div className="mt-6 h-48 animate-pulse rounded-md border border-line bg-surface" />;
  }

  return (
    <Fade k={`code-${resetKey}`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">{heading}</p>

      {!data.available ? (
        <p className="mt-3 text-sm text-ink-soft">
          {data.label
            ? `There's no code to show for ${data.label} yet.`
            : "Nothing was actually kept here, so there's no code to show - it was handed to a human instead."}
        </p>
      ) : (
        <>
          <div className="mt-3 flex items-start gap-3">
            <Mascot className="h-8 w-8 shrink-0" />
            <p className="text-sm text-ink">
              This is the real code behind <span className="font-semibold">{data.label}</span> -
              the exact lines that just ran on your data.
            </p>
          </div>

          <pre className="mt-4 overflow-x-auto rounded-md border border-line bg-bg p-4 text-xs leading-relaxed text-ink">
            <code className="font-mono">{data.code}</code>
          </pre>

          <div className="mt-3 rounded-md border border-points/30 bg-points/10 px-4 py-3 text-sm text-ink">
            <span className="font-semibold">In plain terms: </span>
            {data.explain}
          </div>
        </>
      )}

      <div className="mt-6">
        <Button variant="flat" onClick={onNext}>
          {nextLabel} <span aria-hidden>&rarr;</span>
        </Button>
      </div>
    </Fade>
  );
}
