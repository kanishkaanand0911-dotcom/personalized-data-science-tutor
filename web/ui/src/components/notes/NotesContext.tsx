import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Note = { id: string; text: string; source: string; savedAt: number };

type NotesState = {
  notes: Note[];
  addNote: (text: string, source: string) => void;
  removeNote: (id: string) => void;
  open: boolean;
  setOpen: (v: boolean) => void;
};

const NotesCtx = createContext<NotesState | null>(null);
const STORAGE_KEY = "vybe_notes";

function loadNotes(): Note[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Note[]) : [];
  } catch {
    return [];
  }
}

/* Notes are plain per-browser storage - saved from any chat reply, read back
   on the standalone Notes screen. No backend involved; this is a personal
   scratchpad, not something that needs to sync across devices. */
export function NotesProvider({ children }: { children: ReactNode }) {
  const [notes, setNotes] = useState<Note[]>(() => loadNotes());
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(notes));
    } catch {
      /* storage full/unavailable - notes just won't survive a reload this time */
    }
  }, [notes]);

  const addNote = useCallback((text: string, source: string) => {
    setNotes((ns) => [
      ...ns,
      {
        id: crypto.randomUUID ? crypto.randomUUID() : `note_${Date.now()}_${Math.random().toString(16).slice(2)}`,
        text,
        source,
        savedAt: Date.now(),
      },
    ]);
  }, []);

  const removeNote = useCallback((id: string) => {
    setNotes((ns) => ns.filter((n) => n.id !== id));
  }, []);

  const value = useMemo<NotesState>(
    () => ({ notes, addNote, removeNote, open, setOpen }),
    [notes, addNote, removeNote, open],
  );

  return <NotesCtx.Provider value={value}>{children}</NotesCtx.Provider>;
}

export function useNotes(): NotesState {
  const ctx = useContext(NotesCtx);
  if (!ctx) throw new Error("useNotes must be used within a NotesProvider");
  return ctx;
}
