import { cn } from "@/lib/utils";

export function Tag({
  tone = "neutral",
  children,
}: {
  tone?: "pass" | "fail" | "neutral" | "points";
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide",
        tone === "pass" && "bg-pass/15 text-pass",
        tone === "fail" && "bg-fail/15 text-fail",
        tone === "points" && "border border-points bg-points/15 text-ink",
        tone === "neutral" && "border border-line text-ink-soft",
      )}
    >
      {children}
    </span>
  );
}
