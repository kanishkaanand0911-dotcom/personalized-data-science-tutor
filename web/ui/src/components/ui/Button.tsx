import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "ghost" | "chip" | "flat";

export function Button({
  variant = "primary",
  glow = false,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; glow?: boolean }) {
  // The reference's "Enter the vibe" treatment: a square-ish, bordered,
  // barely-there dark button with a small soft multi-hue glow blurred behind
  // it - not a solid filled pill. Used for every primary/glow button so the
  // whole app reads as one system, not a one-off hero tweak.
  if (variant === "primary" && glow) {
    return (
      <span className={cn("group relative inline-block", props.disabled && "opacity-50")}>
        <span
          className="pointer-events-none absolute -inset-3 rounded-xl opacity-30 blur-lg transition-opacity duration-300 group-hover:opacity-50"
          style={{
            background:
              "linear-gradient(120deg, var(--color-hero), var(--color-points) 55%, var(--color-hero))",
          }}
          aria-hidden
        />
        <button
          className={cn(
            "relative inline-flex items-center gap-2 rounded-lg border border-white/15 bg-white/[0.06] px-5 py-2.5 text-sm font-semibold text-ink backdrop-blur-sm transition-colors duration-200 hover:bg-white/[0.1] disabled:cursor-not-allowed disabled:opacity-40",
            className,
          )}
          {...props}
        >
          {children}
        </button>
      </span>
    );
  }

  return (
    <button
      className={cn(
        "inline-flex items-center gap-2 rounded-[var(--radius-app)] px-5 py-2.5 text-sm font-semibold transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-40",
        variant === "primary" && "bg-hero text-white hover:bg-hero-deep",
        variant === "ghost" &&
          "border border-line bg-transparent text-ink hover:border-hero",
        variant === "chip" &&
          "rounded-full border border-line bg-surface px-4 py-2 text-ink hover:border-hero",
        // Deliberately no glow/gradient - used inside the study screen, which
        // stays flat and quiet on purpose.
        variant === "flat" && "bg-ink text-bg hover:opacity-90",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
