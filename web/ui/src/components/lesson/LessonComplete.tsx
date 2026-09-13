import { motion } from "framer-motion";
import { Mascot } from "@/components/Mascot";
import { Tag } from "@/components/ui/Tag";
import { Button } from "@/components/ui/Button";

export function LessonComplete({
  title,
  pointsEarned,
  pointsTotal,
  nextLabel,
  onNext,
}: {
  title: string;
  pointsEarned: number;
  pointsTotal: number;
  nextLabel: string;
  onNext: () => void;
}) {
  return (
    <div className="flex flex-col items-center py-10 text-center">
      <motion.div
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.35 }}
      >
        <Mascot className="h-16 w-16" />
      </motion.div>
      <p className="mt-4 text-lg text-ink">{title} complete.</p>
      <div className="mt-3">
        <Tag tone="points">+{pointsEarned} points &middot; {pointsTotal} total</Tag>
      </div>
      <div className="mt-7">
        <Button variant="flat" onClick={onNext}>
          {nextLabel} <span aria-hidden>&rarr;</span>
        </Button>
      </div>
    </div>
  );
}
