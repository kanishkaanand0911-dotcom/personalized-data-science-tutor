import { motion } from "framer-motion";
import type { ReactNode } from "react";

/* The one motion treatment for this identity: a calm fade + small upward
   slide. Used for screen transitions and the level reveal. No spring/bounce. */
export function Fade({ children, k }: { children: ReactNode; k?: string | number }) {
  return (
    <motion.div
      key={k}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
