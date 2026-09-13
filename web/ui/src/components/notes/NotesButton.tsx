import { useNotes } from "@/components/notes/NotesContext";

/* Mirrors the mentor's floating button, but small, text-only, and on the
   opposite (left) edge so the two never collide - a quiet affordance on
   every page, not a second thing competing for attention. */
export function NotesButton() {
  const { notes, open, setOpen } = useNotes();

  if (open) return null;

  return (
    <button
      type="button"
      onClick={() => setOpen(true)}
      aria-label="Open notes"
      className="fixed bottom-6 left-6 z-40 flex items-center gap-1.5 rounded-full border border-line bg-surface px-4 py-2.5 text-xs font-semibold text-ink-soft shadow-lg transition-colors hover:border-hero hover:text-ink"
    >
      Notes
      {notes.length > 0 && (
        <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-hero px-1 text-[10px] font-bold text-white">
          {notes.length}
        </span>
      )}
    </button>
  );
}
