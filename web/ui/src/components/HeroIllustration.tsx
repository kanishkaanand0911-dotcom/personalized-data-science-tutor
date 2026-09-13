import { motion } from "framer-motion";
import { Mascot } from "@/components/Mascot";

/* The onboarding hero's right-side composition: the mascot as centerpiece,
   surrounded by small floating "app" cards, a handwritten annotation, and a
   bottom insight card - matching the reference layout element for element. */
export function HeroIllustration() {
  return (
    <div className="relative h-full w-full">
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 h-[380px] w-[380px] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-[0.07] blur-[100px]"
        style={{ background: "var(--color-hero)" }}
        aria-hidden
      />

      {/* mascot, centered */}
      <motion.div
        className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
        animate={{ y: [0, -8, 0] }}
        transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
      >
        <Mascot className="h-40 w-40" />
      </motion.div>

      {/* two distinct icon cards, like the reference: a sheet icon and a grid
          icon, stacked as one loose column to the mascot's left */}
      <FloatCard className="left-[22%] top-[28%]" delay={0.05}>
        <SheetIcon />
      </FloatCard>
      <FloatCard className="left-[20%] top-[60%]" delay={0.15}>
        <GridIcon />
      </FloatCard>

      {/* handwritten annotation, upper-right */}
      <motion.div
        className="absolute right-[6%] top-[24%] max-w-[180px] text-right"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3, duration: 0.5 }}
      >
        <p className="font-hand text-2xl leading-tight text-hero">same data, more you.</p>
        <svg
          className="ml-auto mt-1 h-10 w-14 -scale-x-100"
          viewBox="0 0 60 44"
          fill="none"
          stroke="var(--color-hero)"
          strokeWidth="2"
          strokeLinecap="round"
          aria-hidden
        >
          <path d="M4 4c8 2 20 6 24 16s10 18 26 20" strokeDasharray="1 6" />
          <path d="M46 32l8 8-10 3" />
        </svg>
      </motion.div>

      {/* sparkle accent */}
      <Sparkle className="right-[10%] top-[48%]" />

      {/* cursor accent */}
      <Cursor className="left-[46%] top-[82%]" />

      {/* bottom insight card */}
      <motion.div
        className="absolute bottom-[10%] right-[4%] flex items-center gap-3 border border-white/10 bg-[#151221] px-4 py-3 shadow-[0_18px_40px_-12px_rgba(0,0,0,0.6)]"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.45 }}
      >
        <p className="text-sm font-semibold leading-snug text-ink">
          Messy data
          <br />
          Brighter insights
        </p>
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-hero text-white">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M9 6l6 6-6 6" />
          </svg>
        </span>
      </motion.div>
    </div>
  );
}

function FloatCard({
  className,
  delay,
  children,
}: {
  className: string;
  delay: number;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      className={`absolute flex h-16 w-16 items-center justify-center border border-white/10 bg-[#15121f] ${className}`}
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay, duration: 0.4 }}
    >
      {children}
    </motion.div>
  );
}

function SheetIcon() {
  return (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="4" y="2" width="16" height="20" rx="2.5" fill="#3DDC8A" />
      <rect x="7.5" y="6.5" width="9" height="1.6" rx="0.8" fill="#0f2419" opacity="0.6" />
      <rect x="7.5" y="10.5" width="9" height="1.6" rx="0.8" fill="#0f2419" opacity="0.6" />
      <rect x="7.5" y="14.5" width="6" height="1.6" rx="0.8" fill="#0f2419" opacity="0.6" />
    </svg>
  );
}

function GridIcon() {
  const cells = [0, 1, 2].flatMap((r) => [0, 1, 2].map((c) => [r, c] as const));
  return (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" aria-hidden>
      <defs>
        <linearGradient id="grid-icon-fill" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="var(--color-hero)" />
        </linearGradient>
      </defs>
      {cells.map(([r, c]) => (
        <rect
          key={`${r}-${c}`}
          x={2 + c * 7.5}
          y={2 + r * 7.5}
          width="5.5"
          height="5.5"
          rx="1.2"
          fill="url(#grid-icon-fill)"
          opacity={r === 1 && c === 1 ? 1 : 0.5}
        />
      ))}
    </svg>
  );
}

function Sparkle({ className }: { className: string }) {
  return (
    <motion.svg
      className={`absolute h-4 w-4 ${className}`}
      viewBox="0 0 24 24"
      fill="var(--color-hero)"
      initial={{ opacity: 0, scale: 0.6 }}
      animate={{ opacity: [0.5, 1, 0.5], scale: [0.9, 1.05, 0.9] }}
      transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      aria-hidden
    >
      <path d="M12 2l2 7 7 2-7 2-2 7-2-7-7-2 7-2z" />
    </motion.svg>
  );
}

function Cursor({ className }: { className: string }) {
  return (
    <svg
      className={`absolute h-6 w-6 ${className}`}
      viewBox="0 0 24 24"
      fill="var(--color-ink)"
      stroke="var(--color-bg)"
      strokeWidth="1"
      aria-hidden
    >
      <path d="M4 2l14 6.5-6 1.5-1.5 6z" />
    </svg>
  );
}
