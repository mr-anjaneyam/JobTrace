import { useEffect, useMemo, useRef, type MouseEvent } from 'react';
import { ArrowRight, Bookmark, Check, Columns2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { type Job } from '@/lib/jobs';
import { CompanyMark } from './match-matrix';
import { MiniRadar } from './mini-radar';

export function OpportunityCards({
  jobs,
  selectedId,
  onDetails,
  saved,
  onSave,
  comparing,
  onCompare,
  isNew,
}: {
  jobs: Job[];
  selectedId: string | undefined;
  onDetails: (id: string) => void;
  saved: string[];
  onSave: (id: string) => void;
  comparing: string[];
  onCompare: (id: string) => void;
  isNew: (job: Job) => boolean;
}) {
  const railRef = useRef<HTMLDivElement>(null);

  // Render top 40 matches in the rail for high-performance scrolling and minimal DOM memory
  const visibleJobs = useMemo(() => {
    const top = jobs.slice(0, 40);
    if (selectedId && !top.some((j) => j.id === selectedId)) {
      const sel = jobs.find((j) => j.id === selectedId);
      if (sel) top.push(sel);
    }
    return top;
  }, [jobs, selectedId]);

  useEffect(() => {
    const rail = railRef.current;
    const card = rail?.querySelector<HTMLElement>(`[data-job="${selectedId}"]`);
    if (rail && card) {
      rail.scrollTo({ left: card.offsetLeft - rail.offsetLeft - 5, behavior: 'auto' });
    }
  }, [selectedId]);

  const stop = (event: MouseEvent) => event.stopPropagation();

  return (
    <div className="opportunity-card-rail" ref={railRef}>
      {visibleJobs.map((job) => {
        const isSaved = saved.includes(job.id);
        const isComparing = comparing.includes(job.id);
        return (
          <article
            key={job.id}
            data-job={job.id}
            className={`opportunity-card ${selectedId === job.id ? 'selected' : ''}`}
            onClick={() => onDetails(job.id)}
          >
            <header className="card-head">
              <CompanyMark job={job} />
              <strong className="min-w-0 truncate">{job.company}</strong>
              {isNew(job) && <span className="new-badge">New</span>}
              <Button
                size="icon"
                variant={isSaved ? 'secondary' : 'ghost'}
                className="card-icon"
                aria-label={isSaved ? `Remove ${job.company} from shortlist` : `Add ${job.company} to shortlist`}
                aria-pressed={isSaved}
                onClick={(e) => {
                  stop(e);
                  onSave(job.id);
                }}
              >
                {isSaved ? <Check size={13} /> : <Bookmark size={13} />}
              </Button>
            </header>
            <h3 className="card-title">{job.title}</h3>
            <p className="card-meta">
              {job.location} · {job.seniority}-level · {job.source}
            </p>
            <div className="card-body">
              <div className="card-radar">
                <MiniRadar job={job} />
              </div>
              <div className="card-side">
                <span className="card-score" aria-label={`${job.score}% overall match`}>
                  {job.score}
                  <i>%</i>
                </span>
                <span className="card-side-label">match</span>
                <Button
                  size="icon"
                  variant={isComparing ? 'secondary' : 'ghost'}
                  className="card-icon"
                  aria-label={`Compare ${job.company}`}
                  aria-pressed={isComparing}
                  onClick={(e) => {
                    stop(e);
                    onCompare(job.id);
                  }}
                >
                  <Columns2 size={13} />
                </Button>
              </div>
            </div>
            <Button size="sm" variant="outline" className="card-more" onClick={() => onDetails(job.id)}>
              More info
              <ArrowRight size={12} />
            </Button>
          </article>
        );
      })}
    </div>
  );
}
