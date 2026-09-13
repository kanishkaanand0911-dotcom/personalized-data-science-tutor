import { useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Mascot } from "@/components/Mascot";
import { Button } from "@/components/ui/Button";
import { Segmented } from "@/components/ui/Segmented";
import { api, type LearningMode, type MentorAction } from "@/lib/api";
import { useMentor } from "@/components/mentor/MentorContext";
import { useNotes } from "@/components/notes/NotesContext";

type MentorMsgKind = "chat" | "hint" | "warning" | "explanation" | "success";
type MentorMsg = { from: "you" | "mentor"; text: string; kind: MentorMsgKind; grounded?: boolean };

const SUGGESTED_ACTIONS: { action: MentorAction; label: string }[] = [
  { action: "explain", label: "Explain this" },
  { action: "hint", label: "Give me a hint" },
  { action: "why_wrong", label: "Why is this wrong?" },
  { action: "example", label: "Show an example" },
  { action: "explain_output", label: "Explain the output" },
  { action: "next_step", label: "What should I try next?" },
];

const MODE_LABELS: Record<LearningMode, string> = {
  guided: "Guided",
  assisted: "Assisted",
  independent: "Independent",
};
const MODE_BY_LABEL: Record<string, LearningMode> = {
  Guided: "guided",
  Assisted: "assisted",
  Independent: "independent",
};

function kindOf(action?: MentorAction): MentorMsgKind {
  if (action === "hint") return "hint";
  if (action === "why_wrong") return "warning";
  if (action === "explain" || action === "example" || action === "explain_output" || action === "next_step") {
    return "explanation";
  }
  return "chat";
}

function bubbleClass(kind: MentorMsgKind): string {
  switch (kind) {
    case "hint":
      return "border-points/40 bg-points/10";
    case "warning":
      return "border-fail/40 bg-fail/10";
    case "success":
      return "border-pass/40 bg-pass/10";
    case "explanation":
      return "border-hero/40 bg-hero/10";
    default:
      return "border-line bg-bg";
  }
}

/* The platform-wide AI Mentor: a floating button + slide-out panel, mounted
   once in App.tsx. Reuses the same Card/Button/Mascot/Night-Signal tokens as
   the rest of the app instead of introducing a new visual style - this is an
   overlay, not a redesign, so it works the same regardless of which screen
   (or which screen's own header layout) is currently showing underneath it. */
export function AiMentor() {
  const { open, setOpen, task, mode, setMode, hintsUsed, bumpHints, attemptCount, mistakes, recentActions, logAction } =
    useMentor();
  const { addNote } = useNotes();
  const [messages, setMessages] = useState<MentorMsg[]>([
    {
      from: "mentor",
      text: "Hi, I'm your AI Mentor. Ask me anything about the lesson or dataset you're on, or tap one of the prompts below.",
      kind: "chat",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [live, setLive] = useState<boolean | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const send = async (action?: MentorAction, textOverride?: string) => {
    const text = (textOverride ?? input).trim();
    if (busy || (!text && !action)) return;

    if (text) {
      setMessages((m) => [...m, { from: "you", text, kind: "chat" }]);
      setInput("");
    }
    if (action === "hint") bumpHints();
    logAction(action ?? "chat_message");
    setBusy(true);

    try {
      const res = await api.mentor({
        user_message: text,
        action,
        current_lesson: task.lesson,
        dataset: task.dataset,
        current_code: task.code,
        last_output: task.output,
        last_error: task.error,
        attempt_count: attemptCount,
        hints_used: hintsUsed,
        learning_mode: mode,
        previous_mistakes: mistakes,
        recent_actions: recentActions,
      });
      setLive(res.grounded);
      setMessages((m) => [...m, { from: "mentor", text: res.reply, kind: kindOf(action), grounded: res.grounded }]);
    } catch {
      setMessages((m) => [
        ...m,
        { from: "mentor", text: "Couldn't reach the mentor just now - try again in a moment.", kind: "warning" },
      ]);
    } finally {
      setBusy(false);
      requestAnimationFrame(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }));
    }
  };

  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open AI Mentor"
          className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full border border-white/15 bg-surface shadow-lg transition-transform hover:scale-105"
        >
          <span
            className="pointer-events-none absolute -inset-2 rounded-full opacity-40 blur-md"
            style={{ background: "linear-gradient(120deg, var(--color-hero), var(--color-points) 55%, var(--color-hero))" }}
            aria-hidden
          />
          <Mascot className="relative h-8 w-8" />
        </button>
      )}

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ x: 420, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 420, opacity: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[380px] flex-col border-l border-line bg-surface"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div className="flex items-center gap-2.5">
                <Mascot className="h-8 w-8 shrink-0" />
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-semibold text-ink">AI Mentor</span>
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        busy ? "animate-pulse bg-points" : live === false ? "bg-ink-soft" : "bg-pass"
                      }`}
                      aria-hidden
                    />
                  </div>
                  <span className="text-[10px] text-ink-soft">Your co-pilot - not an answer key</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close mentor"
                className="text-ink-soft hover:text-ink"
              >
                &times;
              </button>
            </div>

            {/* Context summary */}
            <div className="space-y-2 border-b border-line px-4 py-3 text-xs text-ink-soft">
              <div>
                <span className="font-semibold text-ink">Lesson: </span>
                {task.lesson?.title ?? "Not on a lesson yet"}
              </div>
              <div>
                <span className="font-semibold text-ink">Task: </span>
                {task.lesson?.step ?? "—"}
              </div>
              <div>
                <span className="font-semibold text-ink">Dataset: </span>
                {task.dataset?.name ?? "No dataset loaded"}
              </div>
              <Segmented
                options={["Guided", "Assisted", "Independent"]}
                value={MODE_LABELS[mode]}
                onChange={(v) => setMode(MODE_BY_LABEL[v])}
              />
            </div>

            {/* Conversation */}
            <div ref={scrollRef} className="flex-1 space-y-2.5 overflow-y-auto px-4 py-3">
              {messages.map((m, i) => (
                <div key={i} className={`flex ${m.from === "you" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-md border px-3 py-2 text-sm ${
                      m.from === "you" ? "border-hero bg-hero text-white" : `text-ink ${bubbleClass(m.kind)}`
                    }`}
                  >
                    {m.text}
                    {m.from === "mentor" && m.grounded === false && (
                      <div className="mt-1 text-[10px] text-fail">not personalized live yet</div>
                    )}
                    {m.from === "mentor" && (
                      <button
                        type="button"
                        onClick={() => addNote(m.text, task.lesson?.title ?? "AI Mentor")}
                        className="mt-1.5 block text-[10px] font-semibold text-ink-soft hover:text-hero"
                      >
                        Save to notes
                      </button>
                    )}
                  </div>
                </div>
              ))}
              {busy && <p className="text-xs text-ink-soft">thinking&hellip;</p>}
            </div>

            {/* Code-aware quick sends */}
            {(task.code || task.error || task.output) && (
              <div className="flex flex-wrap gap-1.5 border-t border-line px-4 pt-3">
                {task.code && (
                  <button
                    type="button"
                    onClick={() => send("explain", "Can you walk me through this code?")}
                    className="rounded-full border border-line px-3 py-1 text-[11px] text-ink-soft hover:border-hero hover:text-ink"
                  >
                    Send current code
                  </button>
                )}
                {task.error && (
                  <button
                    type="button"
                    onClick={() => send("why_wrong", "I hit this error, can you help me understand it?")}
                    className="rounded-full border border-line px-3 py-1 text-[11px] text-ink-soft hover:border-hero hover:text-ink"
                  >
                    Send last error
                  </button>
                )}
                {task.output && (
                  <button
                    type="button"
                    onClick={() => send("explain_output", "What does this output mean?")}
                    className="rounded-full border border-line px-3 py-1 text-[11px] text-ink-soft hover:border-hero hover:text-ink"
                  >
                    Send last output
                  </button>
                )}
              </div>
            )}

            {/* Suggested actions */}
            <div className="flex flex-wrap gap-1.5 px-4 pt-3">
              {SUGGESTED_ACTIONS.map((a) => (
                <button
                  key={a.action}
                  type="button"
                  disabled={busy}
                  onClick={() => send(a.action)}
                  className="rounded-full border border-line bg-bg px-3 py-1.5 text-[11px] font-medium text-ink-soft transition-colors hover:border-hero hover:text-ink disabled:opacity-40"
                >
                  {a.label}
                </button>
              ))}
            </div>

            {/* Input */}
            <div className="flex gap-2 p-4">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                placeholder="Ask your mentor anything..."
                rows={2}
                disabled={busy}
                className="flex-1 resize-none rounded-md border border-line bg-bg px-3 py-2 text-sm text-ink outline-none focus-visible:border-hero disabled:opacity-50"
              />
              <Button variant="flat" disabled={!input.trim() || busy} onClick={() => send()}>
                Send
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
