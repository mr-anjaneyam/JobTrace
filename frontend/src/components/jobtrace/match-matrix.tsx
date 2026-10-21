import { useState, useEffect, memo } from 'react';
import { ArrowDown, ChevronRight, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { dimensions, scoreBand, type Job } from '@/lib/jobs';

export const CompanyMark = memo(function CompanyMark({ job }: { job: Job }) {
  const [error, setError] = useState(false);
  const colors = {
    ink: 'text-ink bg-muted/60',
    sage: 'text-sage bg-emerald-500/10',
    clay: 'text-clay bg-orange-500/10',
    gold: 'text-gold bg-amber-500/10',
    lilac: 'text-lilac bg-purple-500/10',
  };

  return (
    <span className={`company-mark ${colors[job.brand] || 'text-foreground'}`} aria-hidden="true">
      {job.logoUrl && !error ? (
        <img
          src={job.logoUrl}
          alt={job.company}
          className="company-logo-img"
          loading="lazy"
          onError={() => setError(true)}
        />
      ) : (
        <span className="font-semibold text-[11px] tracking-tight">
          {(job.company || '?').slice(0, 2).toUpperCase()}
        </span>
      )}
    </span>
  );
});

export function MatchMatrix({
  jobs,
  selectedId,
  onSelect,
  reset,
}: {
  jobs: Job[];
  selectedId: string | undefined;
  onSelect: (id: string) => void;
  reset: () => void;
}) {
  const [limit, setLimit] = useState(60);

  // Reset limit whenever search/filters change
  useEffect(() => {
    setLimit(60);
  }, [jobs.length]);

  const visibleJobs = jobs.slice(0, limit);

  return (
    <>
      <div className="matrix-scroll">
        <table className="matrix" aria-label="Job match heatmap">
          <thead>
            <tr>
              <th scope="col">OPPORTUNITY</th>
              <th scope="col">
                <span className="inline-flex items-center gap-1">
                  Match <ArrowDown size={10} />
                </span>
              </th>
              {dimensions.map((d) => (
                <th scope="col" key={d}>
                  {d}
                </th>
              ))}
              <th scope="col" aria-label="Selected" />
            </tr>
          </thead>
          <tbody>
            {visibleJobs.map((job) => (
              <tr key={job.id} className={selectedId === job.id ? 'selected' : ''}>
                <td>
                  <Button
                    variant="ghost"
                    className="job-select"
                    onClick={() => onSelect(job.id)}
                    aria-label={`View ${job.company} ${job.title}`}
                    aria-pressed={selectedId === job.id}
                  >
                    <CompanyMark job={job} />
                    <span className="min-w-0">
                      <span className="block text-[12px] font-semibold">{job.title}</span>
                      <span className="mt-1 block text-[11px] text-muted-foreground">
                        {job.company}
                        <span className="mx-1.5 opacity-50">·</span>
                        {job.location}
                      </span>
                    </span>
                  </Button>
                </td>
                <td>
                  <div className="overall-score" title={`Overall match: ${job.score} out of 100`}>
                    {job.score}
                    <span className="text-[10px] font-normal">%</span>
                  </div>
                </td>
                {job.breakdown.map((score, i) => (
                  <td key={dimensions[i]}>
                    <span
                      className={`score-cell band-${scoreBand(score)}`}
                      title={`${job.company} — ${dimensions[i]}: ${score} out of 100`}
                    >
                      {score}
                    </span>
                  </td>
                ))}
                <td>{selectedId === job.id && <ChevronRight size={14} className="text-primary" />}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {jobs.length > limit && (
          <div className="p-3 text-center border-t border-border bg-muted/30">
            <Button
              variant="outline"
              size="sm"
              className="text-xs gap-1.5 shadow-none"
              onClick={() => setLimit((prev) => prev + 60)}
            >
              <ChevronDown size={13} />
              Show more opportunities (Showing {limit} of {jobs.length})
            </Button>
          </div>
        )}

        {jobs.length === 0 && (
          <div className="py-14 text-center">
            <h3 className="text-lg">No opportunities found</h3>
            <p className="mt-2 text-sm text-muted-foreground">Try broadening your search or filters.</p>
            <Button variant="outline" className="mt-4" onClick={reset}>
              Reset filters
            </Button>
          </div>
        )}
      </div>

      <div className="matrix-footer">
        <span>
          Showing {Math.min(limit, jobs.length)} of {jobs.length} {jobs.length === 1 ? 'opportunity' : 'opportunities'}
        </span>
        <div className="legend">
          <span className="mr-2">Lower fit</span>
          {['low', 'fair', 'good', 'strong', 'excellent'].map((b) => (
            <span key={b} className={`legend-swatch band-${b}`} />
          ))}
          <span className="ml-2">Higher fit</span>
        </div>
      </div>
    </>
  );
}
