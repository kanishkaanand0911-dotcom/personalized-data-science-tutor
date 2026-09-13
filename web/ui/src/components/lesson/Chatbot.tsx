import { useState } from "react";
import { Mascot } from "@/components/Mascot";
import { Button } from "@/components/ui/Button";
import { TutorProgress } from "@/components/lesson/TutorProgress";
import { useNotes } from "@/components/notes/NotesContext";
import { api, type Level, type TutorProgress as TutorProgressT } from "@/lib/api";

type ChatMsg = { from: "you" | "mascot"; text: string };

/* The actual chatbot: real-time Q&A about this lesson, grounded in the
   learner's profile and the current column - see web/chat.py. Typing a fix
   attempt is handled the same way typing a question is; onAttempt decides
   which one it was. The input stays pinned to the bottom of the panel; the
   "what can I even ask" job belongs to the Callouts above, not chips in
   here, so this stays a plain chat. */
export function Chatbot({
  level,
  onAttempt,
  heading = "Chat with your tutor",
}: {
  level: Level;
  onAttempt: (text: string) => Promise<boolean>;
  heading?: string;
}) {
  const [messages, setMessages] = useState<ChatMsg[]>([
    { from: "mascot", text: "Ask me anything about this, or tell me how you'd fix it." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [grounded, setGrounded] = useState<boolean | null>(null);
  const [progress, setProgress] = useState<TutorProgressT | null>(null);
  const { addNote } = useNotes();

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setMessages((m) => [...m, { from: "you", text }]);
    setInput("");
    setBusy(true);
    try {
      const wasAttempt = await onAttempt(text);
      if (!wasAttempt) {
        const res = await api.chat(text, level.id);
        setGrounded(res.grounded);
        if (res.progress) setProgress(res.progress);
        setMessages((m) => [...m, { from: "mascot", text: res.reply }]);
      }
    } catch {
      setMessages((m) => [...m, { from: "mascot", text: "Couldn't reach the tutor just now - try again." }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full min-h-[320px] flex-col rounded-md border border-line bg-surface">
      <div className="flex items-center justify-between border-b border-line px-3 py-2.5">
        <span className="text-sm font-semibold text-ink">{heading}</span>
        {grounded === false && (
          <span className="text-[10px] text-fail">not personalized live yet</span>
        )}
      </div>

      {progress && (
        <div className="px-3 pt-3">
          <TutorProgress progress={progress} />
        </div>
      )}

      <div className="flex-1 space-y-2 overflow-y-auto px-3 py-3">
        {messages.map((m, i) => (
          <div key={i} className={`flex items-start gap-2 ${m.from === "you" ? "justify-end" : ""}`}>
            {m.from === "mascot" && <Mascot className="h-6 w-6 shrink-0" />}
            <div
              className={`max-w-[80%] rounded-md px-3 py-1.5 text-sm ${
                m.from === "you" ? "bg-hero text-white" : "border border-line bg-bg text-ink"
              }`}
            >
              {m.text}
              {m.from === "mascot" && (
                <button
                  type="button"
                  onClick={() => addNote(m.text, level.title)}
                  className="mt-1 block text-[10px] font-semibold text-ink-soft hover:text-hero"
                >
                  Save to notes
                </button>
              )}
            </div>
          </div>
        ))}
        {busy && <p className="text-xs text-ink-soft">thinking&hellip;</p>}
      </div>

      <div className="flex gap-2 border-t border-line p-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask a question, or type your fix"
          className="flex-1 rounded-md border border-line bg-bg px-3 py-2 text-sm text-ink outline-none focus-visible:border-hero"
        />
        <Button variant="flat" disabled={!input.trim() || busy} onClick={send}>
          Send
        </Button>
      </div>
    </div>
  );
}
