import type { CSSProperties } from 'react';
import { ArrowRight, Columns2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { type Job } from '@/lib/jobs';
import { CompanyMark } from './match-matrix';
import { MiniRadar } from './mini-radar';

export function MapPopup({
  job,
  x,
  y,
  width,
  comparing,
  onCompare,
  onMore,
}: {
  job: Job;
  x: number;
  y: number;
  width: number;
  comparing: boolean;
  onCompare: () => void;
  onMore: () => void;
}) {
  const percentX = Math.min(86, Math.max(14, (x / width) * 100));
  const below = y < 180;
  return (
    <div
      role="dialog"
      aria-label={`${job.company} role summary`}
      className={`map-popup ${below ? 'below' : ''}`}
      style={{ '--pop-x': `${percentX}%`, '--pop-y': `${y}px` } as CSSProperties}
    >
      <div className="popup-head">
        <CompanyMark job={job} />
        <div className="min-w-0">
          <strong className="truncate">{job.company}</strong>
          <span className="block truncate">
            {job.source} · {job.location}
          </span>
        </div>
        <span className="popup-score">
          {job.score}
          <i>%</i>
        </span>
      </div>
      <div className="popup-radar">
        <MiniRadar job={job} />
      </div>
      <div className="popup-actions">
        <Button size="sm" className="min-w-0 flex-1" onClick={onMore}>
          More info
          <ArrowRight size={12} />
        </Button>
        <Button
          size="sm"
          variant={comparing ? 'secondary' : 'outline'}
          aria-pressed={comparing}
          onClick={onCompare}
        >
          <Columns2 size={12} />
          {comparing ? 'Added' : 'Compare'}
        </Button>
      </div>
    </div>
  );
}
