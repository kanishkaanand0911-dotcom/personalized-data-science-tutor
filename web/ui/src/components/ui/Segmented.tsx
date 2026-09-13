import { motion } from "framer-motion";

/* A segmented control - visually distinct from the role cards on purpose,
   so two different groups of choices don't read as the same control twice. */
export function Segmented({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string | null;
  onChange: (v: string) => void;
}) {
  return (
    <div className="inline-flex gap-1 rounded-full border border-line bg-surface p-1">
      {options.map((o) => (
        <button
          key={o}
          type="button"
          onClick={() => onChange(o)}
          className="relative rounded-full px-4 py-2 text-sm font-semibold text-ink-soft transition-colors data-[on=true]:text-white"
          data-on={value === o}
        >
          {value === o && (
            <motion.span
              layoutId="segmented-active"
              className="absolute inset-0 rounded-full bg-hero"
              transition={{ type: "spring", stiffness: 500, damping: 34 }}
            />
          )}
          <span className="relative">{o}</span>
        </button>
      ))}
    </div>
  );
}
