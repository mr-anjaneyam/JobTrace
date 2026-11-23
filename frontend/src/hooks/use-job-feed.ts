import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type ApiStateResponse } from '@/lib/api';

export function useJobFeed() {
  const [data, setData] = useState<ApiStateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now() / 1000);
  const clock = useRef({ server: Date.now() / 1000, received: performance.now() });
  const request = useRef<AbortController | null>(null);
  const revision = useRef(0);
  const queued = useRef(false);

  const refresh = useCallback(async () => {
    if (request.current) {
      queued.current = true;
      return;
    }
    const ctrl = new AbortController();
    const startedRevision = revision.current;
    request.current = ctrl;
    try {
      const next = await api.getState(true, ctrl.signal);
      if (!next.timeline) throw new Error('Timeline API unavailable. Update the backend and retry.');
      if (ctrl.signal.aborted) return;
      if (startedRevision !== revision.current) {
        queued.current = true;
        return;
      }
      clock.current = { server: next.timeline.end, received: performance.now() };
      setNow(next.timeline.end);
      setData(next);
      setError(null);
    } catch (err) {
      if (!ctrl.signal.aborted) {
        console.error('JobTrace refresh failed:', err);
        setError(err instanceof Error ? err.message : 'Unable to refresh jobs.');
      }
    } finally {
      if (request.current === ctrl) request.current = null;
      if (queued.current && !ctrl.signal.aborted) {
        queued.current = false;
        void refresh();
      }
    }
  }, []);

  useEffect(() => {
    void refresh();
    const poll = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, 15000);
    const tick = window.setInterval(() => {
      setNow(clock.current.server + (performance.now() - clock.current.received) / 1000);
    }, 1000);
    const resume = () => { if (!document.hidden) void refresh(); };
    window.addEventListener('focus', resume);
    document.addEventListener('visibilitychange', resume);
    return () => {
      window.clearInterval(poll);
      window.clearInterval(tick);
      window.removeEventListener('focus', resume);
      document.removeEventListener('visibilitychange', resume);
      request.current?.abort();
      request.current = null;
      queued.current = false;
    };
  }, [refresh]);

  const markClosed = useCallback((id: string) => {
    revision.current++;
    const closedAt = clock.current.server + (performance.now() - clock.current.received) / 1000;
    setData((current) => {
      if (!current?.timeline) return current;
      return {
        ...current,
        jobs: current.jobs.filter((j) => j.id !== id),
        timeline: {
          ...current.timeline,
          jobs: current.timeline.jobs.map((j) => j.id !== id ? j : {
            ...j, closed_at: closedAt, expires_at: closedAt,
            periods: j.periods?.map((p) => p.closed_at == null ? { ...p, closed_at: closedAt } : p),
          }),
        },
      };
    });
  }, []);

  return { data, error, now, refresh, markClosed };
}
