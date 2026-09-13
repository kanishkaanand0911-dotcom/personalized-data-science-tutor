import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

/* Step 0 - three identity directions to choose between.
   Each tile is fully self-contained: its own palette (scoped CSS vars), font
   pairing, button treatment, and a motion sample. Nothing here is final. */

type Dir = {
  id: string;
  name: string;
  vibe: string;
  display: string;
  body: string;
  vars: Record<string, string>;
  radius: string;
  buttonStyle: "hard-edge" | "flat" | "offset-block";
  motion: "spring-pop" | "calm-fade" | "snappy-wipe";
};

const DIRECTIONS: Dir[] = [
  {
    id: "A",
    name: "Berry Arcade",
    vibe: "Evolves the current Berry Bright. Friendly, tactile, Duolingo energy.",
    display: '"Bricolage Grotesque", sans-serif',
    body: '"Manrope", sans-serif',
    radius: "18px",
    buttonStyle: "hard-edge",
    motion: "spring-pop",
    vars: {
      "--bg": "#FFF7F5",
      "--surface": "#FFFDFB",
      "--ink": "#3A2233",
      "--ink-soft": "#8F7684",
      "--hero": "#FF4785",
      "--hero-deep": "#E23A73",
      "--pass": "#8BC53F",
      "--fail": "#E2703A",
      "--points": "#FFC93C",
      "--line": "#F0DDD6",
    },
  },
  {
    id: "B",
    name: "Study Hall",
    vibe: "Calmer and editorial. Reads as a credible learning tool, not a toy.",
    display: '"Newsreader", serif',
    body: '"Hanken Grotesk", sans-serif',
    radius: "6px",
    buttonStyle: "flat",
    motion: "calm-fade",
    vars: {
      "--bg": "#F6F4EF",
      "--surface": "#FFFFFF",
      "--ink": "#20201D",
      "--ink-soft": "#6B6A63",
      "--hero": "#1F6F5C",
      "--hero-deep": "#155442",
      "--pass": "#1F6F5C",
      "--fail": "#B4462A",
      "--points": "#C08A2E",
      "--line": "#E4E1D8",
    },
  },
  {
    id: "C",
    name: "Bright Lab",
    vibe: "Bold and design-forward. Thick edges, offset color shadows, punchy.",
    display: '"Gabarito", sans-serif',
    body: '"Figtree", sans-serif',
    radius: "14px",
    buttonStyle: "offset-block",
    motion: "snappy-wipe",
    vars: {
      "--bg": "#FBF7F0",
      "--surface": "#FFFFFF",
      "--ink": "#171410",
      "--ink-soft": "#6E655A",
      "--hero": "#FF5A1F",
      "--hero-deep": "#1B4DFF",
      "--pass": "#1FA463",
      "--fail": "#E23D2E",
      "--points": "#FFB302",
      "--line": "#1714100F",
    },
  },
];

function Swatch({ label, color }: { label: string; color: string }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className="h-9 w-9 rounded-md border border-black/10"
        style={{ background: color }}
      />
      <span className="text-[10px] tracking-wide" style={{ color: "var(--ink-soft)" }}>
        {label}
      </span>
    </div>
  );
}

function DemoButton({ dir, children }: { dir: Dir; children: React.ReactNode }) {
  const base = "px-5 py-2.5 font-bold text-sm text-white select-none";
  if (dir.buttonStyle === "hard-edge")
    return (
      <button
        className={base}
        style={{
          background: "var(--hero)",
          borderRadius: 999,
          boxShadow: "0 4px 0 0 var(--hero-deep)",
        }}
        onMouseDown={(e) => (e.currentTarget.style.transform = "translateY(3px)")}
        onMouseUp={(e) => (e.currentTarget.style.transform = "")}
        onMouseLeave={(e) => (e.currentTarget.style.transform = "")}
      >
        {children}
      </button>
    );
  if (dir.buttonStyle === "flat")
    return (
      <button
        className={base}
        style={{ background: "var(--hero)", borderRadius: dir.radius }}
      >
        {children}
      </button>
    );
  return (
    <button
      className={base}
      style={{
        background: "var(--hero)",
        borderRadius: dir.radius,
        border: "2px solid var(--ink)",
        boxShadow: "4px 4px 0 0 var(--ink)",
      }}
      onMouseDown={(e) => {
        e.currentTarget.style.transform = "translate(2px,2px)";
        e.currentTarget.style.boxShadow = "2px 2px 0 0 var(--ink)";
      }}
      onMouseUp={(e) => {
        e.currentTarget.style.transform = "";
        e.currentTarget.style.boxShadow = "4px 4px 0 0 var(--ink)";
      }}
    >
      {children}
    </button>
  );
}

function MotionSample({ dir }: { dir: Dir }) {
  const [n, setN] = useState(0);
  const [key, setKey] = useState(0);
  const run = () => {
    setKey((k) => k + 1);
    setN(0);
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min((t - start) / 700, 1);
      setN(Math.round(p * 10));
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };

  const variants = {
    "spring-pop": {
      initial: { scale: 0.6, opacity: 0, y: 12 },
      animate: { scale: 1, opacity: 1, y: 0 },
      transition: { type: "spring" as const, stiffness: 420, damping: 16 },
    },
    "calm-fade": {
      initial: { opacity: 0, y: 6 },
      animate: { opacity: 1, y: 0 },
      transition: { duration: 0.4, ease: "easeOut" as const },
    },
    "snappy-wipe": {
      initial: { opacity: 0, x: -24, clipPath: "inset(0 100% 0 0)" },
      animate: { opacity: 1, x: 0, clipPath: "inset(0 0% 0 0)" },
      transition: { duration: 0.32, ease: [0.2, 0.8, 0.2, 1] as [number, number, number, number] },
    },
  }[dir.motion];

  return (
    <div className="flex items-center gap-4">
      <DemoButton dir={dir}>
        <span onClick={run}>Run the agent</span>
      </DemoButton>
      <AnimatePresence mode="wait">
        <motion.div
          key={key}
          initial={variants.initial}
          animate={variants.animate}
          transition={variants.transition}
          className="flex items-center gap-3 px-4 py-2"
          style={{
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: dir.radius,
          }}
        >
          <span
            className="text-xs font-bold uppercase tracking-wide"
            style={{
              background: "var(--pass)",
              color: "#fff",
              padding: "2px 8px",
              borderRadius: 999,
            }}
          >
            kept
          </span>
          <span className="text-sm" style={{ color: "var(--ink)" }}>
            skew shift 7.6%
          </span>
          <span
            className="text-sm font-extrabold"
            style={{ color: "var(--points)", fontFamily: dir.display }}
          >
            +{n}
          </span>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function Tile({ dir }: { dir: Dir }) {
  return (
    <section
      className="flex flex-col gap-5 p-7"
      style={
        {
          ...dir.vars,
          background: "var(--bg)",
          color: "var(--ink)",
          fontFamily: dir.body,
          border: "1px solid var(--line)",
          borderRadius: 22,
        } as React.CSSProperties
      }
    >
      <div>
        <div
          className="text-xs font-bold uppercase tracking-[0.15em]"
          style={{ color: "var(--hero-deep)" }}
        >
          Direction {dir.id}
        </div>
        <h2
          className="mt-1 text-3xl"
          style={{ fontFamily: dir.display, fontWeight: 700, color: "var(--ink)" }}
        >
          {dir.name}
        </h2>
        <p className="mt-1 text-sm" style={{ color: "var(--ink-soft)" }}>
          {dir.vibe}
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <Swatch label="hero" color={dir.vars["--hero"]} />
        <Swatch label="bg" color={dir.vars["--bg"]} />
        <Swatch label="ink" color={dir.vars["--ink"]} />
        <Swatch label="pass" color={dir.vars["--pass"]} />
        <Swatch label="fail" color={dir.vars["--fail"]} />
        <Swatch label="points" color={dir.vars["--points"]} />
      </div>

      <div>
        <h3
          className="text-2xl leading-tight"
          style={{ fontFamily: dir.display, fontWeight: 700 }}
        >
          You guessed median imputation. Here is what the agent actually did.
        </h3>
        <p className="mt-2 text-sm" style={{ color: "var(--ink-soft)" }}>
          The same value in every blank cell bent the distribution 21.3%, past the
          15% limit, so the agent discarded it and tried a smarter fill.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <DemoButton dir={dir}>Lock in my guess</DemoButton>
        <button
          className="px-4 py-2 text-sm font-semibold"
          style={{
            borderRadius: 999,
            border: "1.5px solid var(--line)",
            color: "var(--ink)",
          }}
        >
          Sales
        </button>
        <span
          className="px-3 py-1.5 text-xs font-bold"
          style={{
            background: dir.vars["--points"] + "22",
            color: "var(--ink)",
            border: `1.5px solid ${dir.vars["--points"]}`,
            borderRadius: 999,
          }}
        >
          40 points
        </span>
      </div>

      <div className="flex gap-3">
        <div
          className="flex-1 p-3 text-sm"
          style={{
            background: "var(--surface)",
            border: "1.5px solid var(--line)",
            borderRadius: dir.radius,
          }}
        >
          <span style={{ textDecoration: "line-through", color: "var(--ink-soft)" }}>
            Median fill
          </span>{" "}
          <span
            className="text-[10px] font-bold uppercase"
            style={{ color: "var(--fail)" }}
          >
            discarded
          </span>
        </div>
        <div
          className="flex-1 p-3 text-sm"
          style={{
            background: "var(--surface)",
            border: "1.5px solid var(--line)",
            borderRadius: dir.radius,
          }}
        >
          Nearest-neighbor fill{" "}
          <span
            className="text-[10px] font-bold uppercase"
            style={{ color: "var(--pass)" }}
          >
            kept
          </span>
        </div>
      </div>

      <div className="mt-1">
        <div
          className="mb-2 text-[10px] font-bold uppercase tracking-wide"
          style={{ color: "var(--ink-soft)" }}
        >
          motion: {dir.motion.replace("-", " ")}
        </div>
        <MotionSample dir={dir} />
      </div>
    </section>
  );
}

export default function StyleTiles() {
  return (
    <div className="mx-auto max-w-[1180px] px-8 py-12">
      <h1
        className="text-4xl"
        style={{ fontFamily: '"Bricolage Grotesque", sans-serif', fontWeight: 800 }}
      >
        Step 0 - pick a visual direction
      </h1>
      <p className="mt-2 max-w-[60ch] text-sm text-neutral-600">
        Three complete directions: palette, font pairing, button treatment, and
        motion. Click "Run the agent" in each to feel the animation. Nothing is
        locked. Pick one and we tune it, then build screen by screen.
      </p>
      <div className="mt-10 grid gap-6 lg:grid-cols-3">
        {DIRECTIONS.map((d) => (
          <Tile key={d.id} dir={d} />
        ))}
      </div>
    </div>
  );
}
