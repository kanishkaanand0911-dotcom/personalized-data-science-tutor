import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Rail } from "@/components/Rail";
import { Fade } from "@/components/ui/Fade";
import { api, type Level, type Verify as VerifyT, type GuessResult } from "@/lib/api";

export function Verify({
  levels,
  guesses,
  onNext,
}: {
  levels: Level[];
  guesses: Record<number, GuessResult>;
  onNext: () => void;
}) {
  const [data, setData] = useState<VerifyT | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.verify().then(setData).catch((e) => setError(e instanceof Error ? e.message : "Failed to verify."));
  }, []);

  return (
    <div className="mx-auto flex max-w-[1080px] gap-10 px-8 py-14">
      <Rail
        levels={levels}
        completedLevels={new Set(Object.keys(guesses).map(Number))}
        verifyDone={!!data}
        modelDone={false}
        active={{ kind: "verify", label: "Verification" }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-[0.14em] text-hero">
            Verification
          </span>
          <button
            type="button"
            onClick={onNext}
            className="text-xs font-semibold uppercase tracking-[0.1em] text-ink-soft hover:text-ink"
          >
            Skip verification <span aria-hidden>&rarr;</span>
          </button>
        </div>
        {!data ? (
          <p className="mt-3 text-ink-soft">
            {error ?? "Checking the cleaned data can actually be used..."}
          </p>
        ) : (
          <Fade k="verify">
            <h1 className="mt-1 text-4xl text-ink">
              {data.overall_passed ? "The cleaned data holds up" : "Some checks did not pass"}
            </h1>
            <p className="mt-2 max-w-[60ch] text-[15px] text-ink-soft">
              A column can look clean and still break a real task. The agent
              runs the tasks a learner would actually try next.
            </p>
            <div className="mt-6 space-y-3">
              {data.checks.map((c) => (
                <Card key={c.key} className="flex gap-3">
                  <span
                    className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                      c.passed ? "bg-pass/15 text-pass" : "bg-fail/15 text-fail"
                    }`}
                  >
                    {c.passed ? "✓" : "✕"}
                  </span>
                  <div>
                    <div className="font-semibold text-ink">{c.label}</div>
                    <div className="text-sm text-ink-soft">{c.reason}</div>
                  </div>
                </Card>
              ))}
            </div>
            <div className="mt-8">
              <Button glow onClick={onNext}>
                On to modeling <span aria-hidden>&rarr;</span>
              </Button>
            </div>
          </Fade>
        )}
      </div>
    </div>
  );
}
