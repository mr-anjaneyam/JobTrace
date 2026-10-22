import { useEffect, useRef, useState } from 'react';

export type PresenceState = 'open' | 'closed';

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false);

// Keeps the last value mounted for exitMs after it becomes empty so a closing animation can play.
export function usePresence<T>(
  value: T | null | undefined | false,
  exitMs = 240
): { item: T | null; state: PresenceState } {
  const present = value !== null && value !== undefined && value !== false;
  const last = useRef<T | null>(present ? (value as T) : null);
  if (present) last.current = value as T;

  const [mounted, setMounted] = useState(present);

  useEffect(() => {
    if (present) {
      setMounted(true);
      return;
    }
    const timer = setTimeout(() => setMounted(false), prefersReducedMotion() ? 0 : exitMs);
    return () => clearTimeout(timer);
  }, [present, exitMs]);

  return { item: present || mounted ? last.current : null, state: present ? 'open' : 'closed' };
}
