import { useEffect } from "react";
import type { ReactNode } from "react";

/* Shows its children for a fixed beat, then calls onDone. Used to wrap a
   plain scene (like LoadingScene) that has no timing of its own - phased
   scenes like LevelTransition already manage their own timing and don't
   need this. */
export function AutoAdvance({
  ms = 1400,
  onDone,
  children,
}: {
  ms?: number;
  onDone: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const t = setTimeout(onDone, ms);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <>{children}</>;
}
