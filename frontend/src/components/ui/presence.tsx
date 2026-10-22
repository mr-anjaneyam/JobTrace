import type { ReactNode } from 'react';
import { usePresence, type PresenceState } from '@/hooks/use-presence';

export function Presence({
  show,
  exitMs,
  children,
}: {
  show: boolean;
  exitMs?: number;
  children: (state: PresenceState) => ReactNode;
}) {
  const { item, state } = usePresence(show ? true : null, exitMs);
  return item ? <>{children(state)}</> : null;
}
