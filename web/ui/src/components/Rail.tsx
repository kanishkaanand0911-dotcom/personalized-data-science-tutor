import { cn } from "@/lib/utils";
import type { Level } from "@/lib/api";

type Step =
  | { kind: "level"; index: number; label: string }
  | { kind: "verify"; label: string }
  | { kind: "visualize"; label: string }
  | { kind: "mlFoundations"; label: string }
  | { kind: "model"; label: string }
  | { kind: "results"; label: string };

export function Rail({
  levels,
  completedLevels,
  verifyDone,
  visualizeDone = false,
  mlFoundationsDone = false,
  modelDone,
  active,
}: {
  levels: Level[];
  completedLevels: Set<number>;
  verifyDone: boolean;
  visualizeDone?: boolean;
  mlFoundationsDone?: boolean;
  modelDone: boolean;
  active: Step;
}) {
  const steps: Step[] = [
    ...levels.map((l, i): Step => ({ kind: "level", index: i, label: l.title })),
    { kind: "verify", label: "Verification" },
    { kind: "visualize", label: "EDA" },
    { kind: "mlFoundations", label: "ML Foundations" },
    { kind: "model", label: "Model Selection" },
    { kind: "results", label: "Final Project" },
  ];

  const isDone = (s: Step) => {
    if (s.kind === "level") return completedLevels.has(s.index);
    if (s.kind === "verify") return verifyDone;
    if (s.kind === "visualize") return visualizeDone;
    if (s.kind === "mlFoundations") return mlFoundationsDone;
    if (s.kind === "model") return modelDone;
    return false;
  };
  const isActive = (s: Step) =>
    s.kind === active.kind && (s.kind !== "level" || (active.kind === "level" && s.index === active.index));

  return (
    <nav className="w-full shrink-0 border-r border-line pr-6 lg:w-56">
      <div className="mb-3 text-[11px] font-bold uppercase tracking-wide text-ink-soft">
        Your path
      </div>
      <ol className="space-y-1">
        {steps.map((s) => {
          const done = isDone(s);
          const on = isActive(s);
          return (
            <li
              key={s.kind + ("index" in s ? s.index : "")}
              className={cn(
                "flex items-center gap-2 rounded-[var(--radius-app)] px-2 py-1.5 text-sm",
                on ? "bg-hero/8 font-semibold text-ink" : "text-ink-soft",
              )}
            >
              <span
                className={cn(
                  "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border text-[9px]",
                  done ? "border-hero bg-hero text-white" : "border-line",
                  on && !done && "border-hero",
                )}
              >
                {done ? "✓" : ""}
              </span>
              {s.label}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
