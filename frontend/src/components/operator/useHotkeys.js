import { useEffect, useRef } from "react";

/**
 * useHotkeys — global key bindings that ignore typing in inputs.
 *
 * @param {Record<string, (e: KeyboardEvent) => void>} bindings
 *        Keys: lowercased single chars or special names ("escape", "?", " ")
 * @param {boolean} enabled
 */
export default function useHotkeys(bindings, enabled = true) {
  const ref = useRef(bindings);
  ref.current = bindings;

  useEffect(() => {
    if (!enabled) return undefined;

    const handler = (e) => {
      const t = e.target;
      if (!t) return;
      const tag = (t.tagName || "").toUpperCase();
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t.isContentEditable) return;
      // Ignore modifier-only chords (Cmd/Ctrl) so we don't intercept browser shortcuts
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const key = e.key.length === 1 ? e.key.toLowerCase() : e.key.toLowerCase();
      const fn = ref.current[key];
      if (typeof fn === "function") {
        e.preventDefault();
        fn(e);
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [enabled]);
}
