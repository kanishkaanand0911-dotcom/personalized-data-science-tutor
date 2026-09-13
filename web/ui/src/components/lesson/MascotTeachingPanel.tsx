import { Fade } from "@/components/ui/Fade";
import { Mascot } from "@/components/Mascot";

export type MascotMood = "neutral" | "happy" | "confused";

/* The teaching companion, not a decorative illustration: what it says
   changes with every phase and every answer, and its tone (border/text
   color) shifts with the mood the learner's last action earned. */
export function MascotTeachingPanel({
  message,
  mood = "neutral",
}: {
  message: string;
  mood?: MascotMood;
}) {
  return (
    <Fade k={message}>
      <div className="flex items-start gap-3">
        <Mascot className="h-10 w-10 shrink-0" />
        <div
          className={`rounded-md border px-4 py-3 text-sm leading-relaxed ${
            mood === "happy"
              ? "border-pass/30 bg-pass/5 text-ink"
              : mood === "confused"
                ? "border-fail/30 bg-fail/5 text-ink"
                : "border-line bg-surface text-ink"
          }`}
        >
          {message}
        </div>
      </div>
    </Fade>
  );
}
