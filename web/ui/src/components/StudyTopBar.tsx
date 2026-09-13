/* The study screen's own top bar: quieter than the marketing TopBar on
   purpose - a small mark, not the full wordmark, and a plain account circle
   instead of a nav label. Nothing shiny in here. An optional skip action
   (e.g. "Skip cleaning") sits just left of the account circle - the one
   place on this bar meant to be clicked. */
export function StudyTopBar({
  skipLabel,
  onSkip,
}: {
  skipLabel?: string;
  onSkip?: () => void;
}) {
  return (
    <header className="flex items-center justify-between px-6 py-4">
      <span className="flex h-7 w-7 items-center justify-center rounded-md border border-line text-xs font-bold text-ink">
        V
      </span>
      <div className="flex items-center gap-4">
        {onSkip && (
          <button
            type="button"
            onClick={onSkip}
            className="text-xs font-semibold uppercase tracking-[0.1em] text-ink-soft hover:text-ink"
          >
            {skipLabel ?? "Skip"} <span aria-hidden>&rarr;</span>
          </button>
        )}
        <span className="flex h-7 w-7 items-center justify-center rounded-full border border-line text-xs font-semibold text-ink-soft">
          Y
        </span>
      </div>
    </header>
  );
}
