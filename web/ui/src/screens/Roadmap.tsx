import { Mascot } from "@/components/Mascot";
import { Button } from "@/components/ui/Button";
import { topicName } from "@/lib/grading";
import type { Level, Roadmap as RoadmapT } from "@/lib/api";

type Step = { key: string; label: string };

export function Roadmap({
  roadmap,
  levels,
  onStart,
}: {
  roadmap: RoadmapT;
  levels: Level[];
  hasLevels: boolean;
  onStart: () => void;
}) {
  // The full course, in order: exploration, then one real step per detected
  // issue (not a generic "Cleaning" bucket), then the backend's own
  // verify/model/results phases.
  const steps: Step[] = [
    { key: "explore", label: "Python & Data Fundamentals" },
    ...levels.map((l) => ({ key: `level-${l.id}`, label: `${topicName(l.issue_type)} — ${l.column}` })),
    ...roadmap.nodes.slice(1).map((n) => ({ key: n.key, label: n.title })),
  ];

  // Roadmap is only ever shown before any step has run, so step 0 is always
  // "up next" and everything after it is locked - this becomes real
  // per-step progress once the app lets a learner navigate back here mid-way.
  const doneCount = 0;
  const currentIndex = 0;
  const progressPct = Math.round((doneCount / steps.length) * 100);

  return (
    <div className="mx-auto max-w-[880px] px-8 py-16">
      <div className="flex flex-col gap-8 sm:flex-row sm:items-center">
        <RoadmapArt />
        <div className="min-w-0 flex-1">
          <span className="text-xs font-bold uppercase tracking-[0.14em] text-hero">
            Your path through {roadmap.dataset_name}
          </span>
          <h1 className="mt-2 text-4xl leading-[1.05] text-ink sm:text-5xl">
            Since it&rsquo;s your data, here&rsquo;s your path
          </h1>

          <div className="mt-5 flex items-center gap-3">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line">
              <div
                className="h-full rounded-full bg-hero transition-[width] duration-300"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="text-xs text-ink-soft">{progressPct}%</span>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-4">
            <Button glow onClick={onStart}>
              Continue <span aria-hidden>&rarr;</span>
            </Button>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-soft">Up next</p>
              <p className="text-sm font-semibold text-ink">{steps[currentIndex].label}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-14">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl text-ink">Contents</h2>
          <span className="text-sm text-ink-soft">
            {doneCount} of {steps.length} complete
          </span>
        </div>

        <ol className="mt-6">
          {steps.map((step, i) => {
            const done = i < doneCount;
            const current = i === currentIndex;
            const locked = !done && !current;
            return (
              <li key={step.key} className="relative flex items-center gap-4 pb-7 last:pb-0">
                {i < steps.length - 1 && (
                  <div
                    className={`absolute left-[15px] top-8 h-full w-px ${done ? "bg-pass" : "bg-line"}`}
                  />
                )}
                <div
                  className={`z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold ${
                    done
                      ? "border-pass bg-pass text-[#0d1a10]"
                      : current
                        ? "border-hero text-hero"
                        : "border-line text-ink-soft"
                  }`}
                >
                  {done ? (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      <path d="M4 12l5 5L20 6" />
                    </svg>
                  ) : (
                    i + 1
                  )}
                </div>
                <span
                  className={`flex-1 text-sm font-semibold ${
                    current ? "text-ink" : locked ? "text-ink-soft" : "text-ink"
                  } ${current ? "rounded-md border border-hero/40 bg-hero/5 px-3 py-2" : ""}`}
                >
                  {step.label}
                </span>
                {locked ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-ink-soft" aria-hidden>
                    <rect x="5" y="11" width="14" height="9" rx="2" />
                    <path d="M8 11V8a4 4 0 018 0v3" />
                  </svg>
                ) : done ? (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="text-pass" aria-hidden>
                    <path d="M4 12l5 5L20 6" />
                  </svg>
                ) : null}
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

function RoadmapArt() {
  return (
    <div className="relative flex h-28 w-28 shrink-0 items-center justify-center overflow-hidden rounded-md border border-line bg-surface">
      <div
        className="pointer-events-none absolute h-24 w-24 rounded-full opacity-[0.14] blur-2xl"
        style={{ background: "var(--color-hero)" }}
        aria-hidden
      />
      <Mascot className="relative h-14 w-14" />
      <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-points" aria-hidden />
      <span className="absolute bottom-2 left-2 h-2 w-2 rotate-45 bg-hero/50" aria-hidden />
    </div>
  );
}
