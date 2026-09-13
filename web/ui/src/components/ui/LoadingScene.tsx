import { motion } from "framer-motion";
import { Mascot } from "@/components/Mascot";

export function LoadingScene({ label }: { label: string }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-bg px-8 text-center">
      <motion.div
        animate={{ y: [0, -10, 0] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
      >
        <Mascot className="h-24 w-24" />
      </motion.div>
      <p className="mt-8 max-w-[36ch] text-2xl leading-snug text-ink">{label}</p>
      <div className="mt-6 flex gap-1.5">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="h-1.5 w-1.5 rounded-full bg-hero"
            animate={{ opacity: [0.25, 1, 0.25] }}
            transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.15, ease: "easeInOut" }}
          />
        ))}
      </div>
    </div>
  );
}
