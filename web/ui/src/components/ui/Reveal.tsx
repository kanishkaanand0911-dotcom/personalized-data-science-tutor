import { motion } from "framer-motion";
import type { ReactNode } from "react";

/* Scroll-reveal: fades/slides an element up as it enters the viewport, once.
   Same calm-fade motion values as Fade.tsx, just triggered by viewport entry
   instead of mount, and with an optional stagger delay. */
export function Reveal({
  children,
  delay = 0,
}: {
  children: ReactNode;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.45, ease: "easeOut", delay }}
    >
      {children}
    </motion.div>
  );
}
