import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { LearningMode, MentorDatasetContext, MentorLessonContext } from "@/lib/api";

/* What "where the learner currently is" means to the mentor. App.tsx already
   tracks screen/dataset/level state for routing, so it also computes this and
   pushes it in here - no other screen needs to be touched to wire the
   mentor up. */
export type MentorTaskContext = {
  lesson?: MentorLessonContext;
  dataset?: MentorDatasetContext;
  code?: string;
  output?: string;
  error?: string;
};

type MentorState = {
  open: boolean;
  setOpen: (v: boolean) => void;
  task: MentorTaskContext;
  setTask: (patch: Partial<MentorTaskContext>) => void;
  mode: LearningMode;
  setMode: (m: LearningMode) => void;
  hintsUsed: number;
  bumpHints: () => void;
  attemptCount: number;
  bumpAttempts: () => void;
  mistakes: string[];
  addMistake: (m: string) => void;
  recentActions: string[];
  logAction: (a: string) => void;
};

const MentorCtx = createContext<MentorState | null>(null);

export function MentorProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [task, setTaskState] = useState<MentorTaskContext>({});
  const [mode, setMode] = useState<LearningMode>("assisted");
  const [hintsUsed, setHintsUsed] = useState(0);
  const [attemptCount, setAttemptCount] = useState(0);
  const [mistakes, setMistakes] = useState<string[]>([]);
  const [recentActions, setRecentActions] = useState<string[]>([]);

  const bumpHints = useCallback(() => setHintsUsed((n) => n + 1), []);
  const bumpAttempts = useCallback(() => setAttemptCount((n) => n + 1), []);
  const addMistake = useCallback((m: string) => setMistakes((ms) => [...ms, m].slice(-10)), []);
  const logAction = useCallback((a: string) => setRecentActions((as) => [...as, a].slice(-10)), []);

  // Merges rather than replaces, so a screen can push just {code}/{output}/
  // {error} without clobbering the {lesson, dataset} App.tsx already set for
  // the current screen. A new lesson id shouldn't inherit the last one's
  // hint/attempt tally.
  const setTask = useCallback((patch: Partial<MentorTaskContext>) => {
    setTaskState((prev) => {
      const next = { ...prev, ...patch };
      if ("lesson" in patch && patch.lesson?.id !== prev.lesson?.id) {
        setHintsUsed(0);
        setAttemptCount(0);
      }
      return next;
    });
  }, []);

  const value = useMemo<MentorState>(
    () => ({
      open,
      setOpen,
      task,
      setTask,
      mode,
      setMode,
      hintsUsed,
      bumpHints,
      attemptCount,
      bumpAttempts,
      mistakes,
      addMistake,
      recentActions,
      logAction,
    }),
    [open, task, setTask, mode, hintsUsed, bumpHints, attemptCount, bumpAttempts, mistakes, addMistake, recentActions, logAction],
  );

  return <MentorCtx.Provider value={value}>{children}</MentorCtx.Provider>;
}

export function useMentor(): MentorState {
  const ctx = useContext(MentorCtx);
  if (!ctx) throw new Error("useMentor must be used within a MentorProvider");
  return ctx;
}
