import { StudyTopBar } from "@/components/StudyTopBar";
import { Tag } from "@/components/ui/Tag";

/* Compact header: brand (via StudyTopBar), current mission, and progress -
   nothing else competes for space up here. */
export function LessonHeader({
  mission,
  title,
  points,
  progress,
  skipLabel,
  onSkip,
}: {
  mission: string;
  title: string;
  points: number;
  progress: number; // 0-1
  skipLabel?: string;
  onSkip?: () => void;
}) {
  return (
    <div>
      <StudyTopBar skipLabel={skipLabel} onSkip={onSkip} />
      <div className="h-0.5 w-full bg-line">
        <div
          className="h-full bg-hero transition-[width] duration-300"
          style={{ width: `${Math.round(progress * 100)}%` }}
        />
      </div>
      <div className="mx-auto flex max-w-[640px] items-center justify-between px-6 pt-4">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
          {mission} &middot; {title}
        </span>
        <Tag tone="points">{points} points</Tag>
      </div>
    </div>
  );
}
