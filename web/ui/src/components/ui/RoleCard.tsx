import { cn } from "@/lib/utils";

/* Square, bordered, grayish-transparent - not another oval chip. Distinct
   from Segmented on purpose. */
export function RoleCard({
  label,
  blurb,
  selected,
  onClick,
}: {
  label: string;
  blurb: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-lg border px-4 py-3 text-left transition-colors",
        selected ? "border-hero bg-hero/10" : "border-white/10 bg-white/[0.04] hover:border-white/25",
      )}
    >
      <div className="text-sm font-semibold text-ink">{label}</div>
      <div className="mt-0.5 text-xs text-ink-soft">{blurb}</div>
    </button>
  );
}
