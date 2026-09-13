import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mascot } from "@/components/Mascot";
import { Tag } from "@/components/ui/Tag";

/* Full-screen beat between levels. Plays each phase in `phases` in order
   (e.g. ["Level 1 completed", "Level 2 started"]), then calls onDone. */
export function LevelTransition({
  phases,
  points,
  onDone,
  phaseMs = 1100,
}: {
  phases: string[];
  points: number;
  onDone: () => void;
  phaseMs?: number;
}) {
  const [i, setI] = useState(0);

  useEffect(() => {
    if (i >= phases.length) {
      onDone();
      return;
    }
    const t = setTimeout(() => setI((n) => n + 1), phaseMs);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i]);

  const phase = phases[Math.min(i, phases.length - 1)];

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-bg px-8 text-center">
      <motion.div
        animate={{ y: [0, -10, 0] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
      >
        <Mascot className="h-24 w-24" />
      </motion.div>

      <AnimatePresence mode="wait">
        <motion.p
          key={phase}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.25 }}
          className="mt-7 text-2xl text-ink"
        >
          {phase}
        </motion.p>
      </AnimatePresence>

      <div className="mt-5 h-1 w-48 overflow-hidden rounded-full bg-white/10">
        <motion.div
          key={i}
          className="h-full bg-hero"
          initial={{ width: "0%" }}
          animate={{ width: "100%" }}
          transition={{ duration: phaseMs / 1000, ease: "easeInOut" }}
        />
      </div>

      <div className="mt-6">
        <Tag tone="points">{points} points</Tag>
      </div>
    </div>
  );
}
