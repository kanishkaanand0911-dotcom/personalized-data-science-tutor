import { cn } from "@/lib/utils";

/* One centered, label-only option for the onboarding quiz steps - no
   descriptor line, square corners, same grayish-transparent system as the
   rest of the app. */
export function QuizOption({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full max-w-[320px] border px-6 py-3.5 text-center text-sm font-semibold transition-colors",
        selected
          ? "border-hero bg-hero/10 text-ink"
          : "border-white/10 bg-white/[0.03] text-ink-soft hover:border-white/25 hover:text-ink",
      )}
    >
      {label}
    </button>
  );
}
