import { useCallback, useEffect, useRef, useState } from 'react';
import { defaultWorkspace, loadWorkspace, saveWorkspace, type WorkspaceState } from '@/lib/workspace';
import { isMapAxis } from '@/lib/jobs';

const DAY_MS = 24 * 60 * 60 * 1000;

export function useWorkspace() {
  const [state, setState] = useState<WorkspaceState>(() => defaultWorkspace());
  const [newDays, setNewDays] = useState(0);
  const ready = useRef(false);

  useEffect(() => {
    const stored = loadWorkspace();
    const now = Date.now();
    const firstVisit = !stored;
    const since = firstVisit ? now - 2 * DAY_MS : typeof stored?.lastVisit === 'number' ? stored.lastVisit : now;
    setNewDays(Math.max(0, Math.floor((now - since) / DAY_MS)));

    setState((current) => {
      const merged: WorkspaceState = {
        ...current,
        ...stored,
        saved: Array.isArray(stored?.saved) ? stored.saved.filter((id) => typeof id === 'string') : current.saved,
        minimum: typeof stored?.minimum === 'number' ? Math.min(100, Math.max(0, stored.minimum)) : current.minimum,
        threshold: typeof stored?.threshold === 'number' ? Math.min(75, Math.max(25, stored.threshold)) : current.threshold,
        xAxis: isMapAxis(stored?.xAxis ?? '') ? (stored?.xAxis as WorkspaceState['xAxis']) : current.xAxis,
        yAxis: isMapAxis(stored?.yAxis ?? '') ? (stored?.yAxis as WorkspaceState['yAxis']) : current.yAxis,
        seniority: typeof stored?.seniority === 'string' ? stored.seniority : current.seniority,
        location: typeof stored?.location === 'string' ? stored.location : current.location,
        source: typeof stored?.source === 'string' ? stored.source : current.source,
        search: typeof stored?.search === 'string' ? stored.search : current.search,
        shortlistOnly: typeof stored?.shortlistOnly === 'boolean' ? stored.shortlistOnly : current.shortlistOnly,
        lastVisit: now,
      };
      return merged;
    });
    ready.current = true;
  }, []);

  useEffect(() => {
    if (ready.current) saveWorkspace(state);
  }, [state]);

  const patch = useCallback((partial: Partial<WorkspaceState>) => {
    setState((current) => ({ ...current, ...partial }));
  }, []);

  return { state, patch, newDays };
}
