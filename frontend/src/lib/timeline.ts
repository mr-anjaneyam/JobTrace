import type { ApiJob } from './api';

export const HISTORY_SECONDS = 30 * 86400;

export function isJobActiveAt(job: ApiJob, at: number): boolean {
  const periods = job.periods ?? [{ opened_at: job.first_seen, closed_at: job.closed_at }];
  return periods.some((period) => {
    if (period.opened_at == null || period.opened_at > at) return false;
    const end = period.closed_at ?? job.expires_at ?? job.deadline_at;
    return end == null || at < end;
  });
}
