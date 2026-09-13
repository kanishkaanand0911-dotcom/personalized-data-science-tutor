import { motion } from "framer-motion";

/* Self-animating cue, not scroll-triggered: the arrow moves on its own in a
   short loop. Used sparingly - one per page, near the thing worth continuing
   toward, never as a generic decoration. */
export function DownHint({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-1 text-ink-soft">
      {label && <span className="text-xs">{label}</span>}
      <motion.svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        animate={{ y: [0, 5, 0] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
      >
        <path d="M12 5v14M6 13l6 6 6-6" />
      </motion.svg>
    </div>
  );
}
