import { useCallback, useRef, useState } from "react";

/**
 * Server-side cooldown is authoritative (1500ms). This hook adds a UX-layer
 * instant disable + 1500ms timeout so the user can't double-click.
 */
export default function useOrderCooldown(ms = 1500) {
  const [locked, setLocked] = useState(false);
  const lockUntil = useRef(0);

  const arm = useCallback(() => {
    lockUntil.current = Date.now() + ms;
    setLocked(true);
    setTimeout(() => {
      if (Date.now() >= lockUntil.current) setLocked(false);
    }, ms);
  }, [ms]);

  return { locked, arm };
}
