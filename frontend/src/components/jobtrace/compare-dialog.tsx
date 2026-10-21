import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from 'recharts';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { dimensions, type Job } from '@/lib/jobs';
import { CompanyMark } from './match-matrix';

function CompareRadar({ job }: { job: Job }) {
  const data = dimensions.map((dimension, i) => ({ dimension, value: job.breakdown[i] ?? 0 }));
  return (
    <div
      className="compare-radar"
      role="img"
      aria-label={`${job.company} radar: ${dimensions.map((d, i) => `${d} ${job.breakdown[i] ?? 0}`).join(', ')}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%" margin={{ top: 6, bottom: 2, left: 6, right: 6 }}>
          <PolarGrid stroke="var(--border)" />
          <PolarAngleAxis dataKey="dimension" tickLine={false} tick={{ fontSize: 9, fill: 'var(--muted-foreground)' }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Radar
            dataKey="value"
            stroke="var(--primary)"
            fill="var(--primary)"
            fillOpacity={0.16}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CompareDialog({
  jobs,
  open,
  onOpenChange,
}: {
  jobs: Job[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const pair: [Job, Job] | null = jobs.length >= 2 && jobs[0] && jobs[1] ? [jobs[0], jobs[1]] : null;
  if (!pair) return null;
  const [a, b] = pair;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="compare-dialog">
        <DialogTitle className="sr-only">
          Compare {a.company} and {b.company}
        </DialogTitle>
        <h2 className="compare-title">Side-by-side comparison</h2>
        <p className="compare-sub">Higher dimension scores show where each role fits your profile best.</p>
        <div className="compare-grid">
          {[a, b].map((job) => (
            <div className="compare-col" key={job.id}>
              <div className="compare-head">
                <CompanyMark job={job} />
                <div className="min-w-0">
                  <strong className="truncate">{job.company}</strong>
                  <span className="truncate">{job.title}</span>
                </div>
                <span className="popup-score">
                  {job.score}
                  <i>%</i>
                </span>
              </div>
              <CompareRadar job={job} />
            </div>
          ))}
        </div>
        <div className="compare-dims">
          {dimensions.map((d, i) => {
            const va = a.breakdown[i] ?? 0;
            const vb = b.breakdown[i] ?? 0;
            const win = va === vb ? null : va > vb ? a.id : b.id;
            return (
              <div className="compare-dim-row" key={d}>
                <strong data-win={win === a.id}>{va}</strong>
                <span>{d}</span>
                <strong data-win={win === b.id}>{vb}</strong>
              </div>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
