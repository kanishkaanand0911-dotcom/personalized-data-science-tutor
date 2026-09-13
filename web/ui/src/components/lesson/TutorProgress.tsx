import type { TutorProgress as TutorProgressT } from "@/lib/api";

/* Real structured data from the ADK tutor's own gamification agent (XP,
   level, badges) rendered as an actual UI element - not just left sitting
   inside a sentence of chat text. Shows up the moment the tutor's reply
   carries progress, and stays until the level unmounts. */
export function TutorProgress({ progress }: { progress: TutorProgressT }) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 text-xs">
      <span className="rounded-full bg-hero/15 px-2 py-0.5 font-semibold text-hero">
        Lvl {progress.level}
      </span>
      <span className="text-ink-soft">{progress.xp} XP</span>
      {progress.badges.map((badge) => (
        <span
          key={badge}
          className="rounded-full border border-points/40 bg-points/10 px-2 py-0.5 text-points"
        >
          {badge.replace(/_/g, " ")}
        </span>
      ))}
      <span className="ml-auto text-[10px] uppercase tracking-wide text-ink-soft">tutor progress</span>
    </div>
  );
}
