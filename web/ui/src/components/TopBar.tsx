export function TopBar({
  right = "No PhD required",
  onRightClick,
}: {
  right?: string;
  onRightClick?: () => void;
}) {
  return (
    <header className="flex items-center justify-between px-8 py-5 lg:px-16">
      <span className="font-display text-lg font-bold text-ink">VYBE Learn</span>
      {onRightClick ? (
        <button
          type="button"
          onClick={onRightClick}
          className="text-xs font-semibold uppercase tracking-[0.14em] text-hero hover:text-ink"
        >
          {right}
        </button>
      ) : (
        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-hero">{right}</span>
      )}
    </header>
  );
}
