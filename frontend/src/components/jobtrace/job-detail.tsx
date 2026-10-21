import { useEffect, useState, type CSSProperties } from 'react';
import { Bookmark, Check, MapPin, Sparkles, ChevronDown, ChevronUp, Clock3, ExternalLink } from 'lucide-react';
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from 'recharts';
import { Button } from '@/components/ui/button';
import { dimensions, type Job } from '@/lib/jobs';
import { api } from '@/lib/api';
import { CompanyMark } from './match-matrix';

export function JobDetail({
  job,
  saved,
  onSave,
}: {
  job: Job | undefined;
  saved: boolean;
  onSave: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [fullDesc, setFullDesc] = useState<string | null>(null);

  useEffect(() => {
    setFullDesc(null);
  }, [job?.id]);

  useEffect(() => {
    if (expanded && job && !fullDesc) {
      api.getJobDetail(job.id)
        .then((detail) => {
          if (detail.description) setFullDesc(detail.description);
        })
        .catch(() => {});
    }
  }, [expanded, job?.id, fullDesc]);

  if (!job) {
    return (
      <aside className="tool p-8 text-center">
        <h2 className="text-lg">Match breakdown</h2>
        <p className="mt-3 text-muted-foreground">No role matches your current filters.</p>
      </aside>
    );
  }

  const radarData = dimensions.map((dimension, i) => ({ dimension, value: job.breakdown[i] ?? 0 }));

  return (
    <aside className="tool detail-tool" aria-label="Selected role details">
      <div className="detail-header">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-[15px] font-medium">Match breakdown</h2>
          <Sparkles size={15} className="text-gold" />
        </div>
        <div className="flex items-start gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <CompanyMark job={job} />
            <div className="min-w-0">
              <h3 className="text-base font-medium truncate">{job.company}</h3>
              <p className="text-[11px] text-muted-foreground">{job.source}</p>
            </div>
          </div>
          <span className="ml-auto inline-flex shrink-0 items-center gap-1.5 rounded-sm bg-secondary px-2 py-1 text-[10px] text-primary">
            <span className="size-1 rounded-full bg-primary" />
            Active
          </span>
        </div>
        <h3 className="mt-4 text-[17px] font-medium leading-snug">{job.title}</h3>
        <p className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
          <MapPin size={12} />
          {job.location}
          <span className="mx-1">·</span>
          {job.seniority}-level
        </p>
      </div>

      <div className="detail-body">
        <div className="flex items-center gap-3">
          <div className="score-ring" aria-label={`${job.score}% overall match`}>
            {job.score}
            <span className="sr-only">%</span>
          </div>
          <div>
            <p className="font-display text-base font-medium">
              {job.score >= 85
                ? 'An excellent match'
                : job.score >= 70
                ? 'A strong match'
                : job.score >= 55
                ? 'A promising match'
                : 'Room to grow'}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">Overall fit for your profile</p>
          </div>
        </div>

        <div
          className="radar-wrap"
          role="img"
          aria-label={`${job.company} radar: ${dimensions.map((d, i) => `${d} ${job.breakdown[i]}`).join(', ')}`}
        >
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="68%" margin={{ top: 15, bottom: 15, left: 12, right: 12 }}>
              <PolarGrid stroke="var(--border)" />
              <PolarAngleAxis dataKey="dimension" tickLine={false} />
              <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
              <Radar
                dataKey="value"
                stroke="var(--primary)"
                fill="var(--primary)"
                fillOpacity={0.15}
                strokeWidth={2}
                dot={{ r: 3, fill: 'var(--primary)', strokeWidth: 0 }}
                isAnimationActive={false}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="flex items-center justify-center gap-2 text-[10px] text-muted-foreground">
          <span className="size-2 rounded-full bg-primary" />
          Match to your profile
        </div>

        <div className="dimension-list">
          {dimensions.map((d, i) => (
            <div key={d}>
              <div className="flex justify-between text-[11px]">
                <span className="text-muted-foreground">{d}</span>
                <span className="font-medium">
                  {job.breakdown[i]}
                  <span className="text-muted-foreground"> / 100</span>
                </span>
              </div>
              <div className="dimension-bar">
                <div
                  className="dimension-fill"
                  style={{ '--score-width': `${job.breakdown[i]}%` } as CSSProperties}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="detail-body detail-lower border-t border-border">
        <h3 className="mb-3 flex items-center gap-2 text-[13px] font-medium">
          <Sparkles size={14} className="text-primary" />
          Why this role fits
        </h3>
        <p className="reason">{job.reason}</p>
        <div className="my-4 flex flex-wrap gap-1.5">
          {job.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-sm border border-border px-2 py-1 text-[10px] text-muted-foreground"
            >
              {tag}
            </span>
          ))}
        </div>

        <div className="flex flex-col gap-2">
          {job.url && job.url !== '#' && (
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 w-full h-9 rounded-md bg-primary text-primary-foreground text-sm font-medium shadow hover:bg-primary/90 transition-colors"
            >
              <ExternalLink size={14} />
              View opening on {job.company}
            </a>
          )}
          <Button onClick={onSave} className="w-full" variant={saved ? 'secondary' : 'outline'}>
            {saved ? <Check size={14} /> : <Bookmark size={14} />}
            {saved ? 'Shortlisted' : 'Add to shortlist'}
          </Button>
        </div>

        <Button
          variant="ghost"
          className="mt-2 w-full text-xs text-muted-foreground"
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
        >
          Role details {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </Button>

        {expanded && (
          <div className="mt-3 border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground whitespace-pre-line max-h-60 overflow-y-auto pr-1">
            <p>{fullDesc || job.description}</p>
            <p className="mt-3 flex items-center gap-1 font-medium text-foreground">
              <Clock3 size={12} />
              {job.daysAgo === 0 ? 'Discovered today' : `First seen ${job.daysAgo} day${job.daysAgo === 1 ? '' : 's'} ago`} · {job.source}
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}
