import { useId } from "react";

/* Thin-outline mascot, consistent with the panel's dot/line visual language -
   no filled cartoon block, just a stroked creature. The outline itself is a
   soft pink-to-white blend, not a flat single color. */
export function Mascot({ className }: { className?: string }) {
  const gradId = `mascot-stroke-${useId().replace(/:/g, "")}`;
  return (
    <svg
      viewBox="0 0 120 120"
      className={className}
      fill="none"
      strokeWidth="2"
      aria-hidden
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="55%" stopColor="#ffd7ec" />
          <stop offset="100%" stopColor="var(--color-hero)" />
        </linearGradient>
      </defs>
      <g stroke={`url(#${gradId})`}>
        <path d="M60 22c-2-8 4-14 10-16" strokeLinecap="round" />
        <circle cx="71" cy="6" r="3" fill={`url(#${gradId})`} stroke="none" />
        <rect x="24" y="24" width="72" height="66" rx="30" />
        <circle cx="48" cy="54" r="4" fill={`url(#${gradId})`} stroke="none" />
        <circle cx="72" cy="54" r="4" fill={`url(#${gradId})`} stroke="none" />
        <path d="M46 68c4 6 12 6 16 0" strokeLinecap="round" />
      </g>
    </svg>
  );
}
