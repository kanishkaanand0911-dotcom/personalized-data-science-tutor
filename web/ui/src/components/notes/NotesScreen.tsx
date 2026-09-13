import { AnimatePresence, motion } from "framer-motion";
import { useNotes } from "@/components/notes/NotesContext";

/* Deliberately plain: no cards-within-cards, no charts, just the saved text
   itself, centered, in the order it was saved - a scratchpad, not another
   lesson screen. */
export function NotesScreen() {
  const { notes, removeNote, open, setOpen } = useNotes();

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 overflow-y-auto bg-bg"
        >
          <div className="mx-auto max-w-[640px] px-6 py-14">
            <div className="flex items-center justify-between">
              <h1 className="text-2xl text-ink">Notes</h1>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close notes"
                className="text-2xl leading-none text-ink-soft hover:text-ink"
              >
                &times;
              </button>
            </div>

            {notes.length === 0 ? (
              <p className="mt-8 text-sm text-ink-soft">
                Nothing saved yet - look for &ldquo;Save to notes&rdquo; under a mentor reply.
              </p>
            ) : (
              <div className="mt-8 space-y-4">
                {notes.map((n) => (
                  <div key={n.id} className="rounded-[var(--radius-app)] border border-line bg-surface p-4">
                    <div className="flex items-start justify-between gap-3">
                      <span className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                        {n.source}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeNote(n.id)}
                        aria-label="Remove note"
                        className="text-ink-soft hover:text-fail"
                      >
                        &times;
                      </button>
                    </div>
                    <p className="mt-2 text-sm text-ink">{n.text}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
