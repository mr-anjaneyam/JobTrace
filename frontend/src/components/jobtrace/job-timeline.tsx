import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { Pause, Play, Radio } from 'lucide-react';
import { HISTORY_SECONDS } from '@/lib/timeline';
import '@/timeline.css';

type Props = {
  now: number;
  value: number | null;
  onChange: (value: number | null) => void;
  count: number;
  loading: boolean;
  truncated: boolean;
};

const dateLabel = (value: number) => new Date(value * 1000).toLocaleString([], {
  month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
});

export function JobTimeline({ now, value, onChange, count, loading, truncated }: Props) {
  const [playing, setPlaying] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const cursor = useRef(value);
  const end = useRef(now);
  cursor.current = value;
  end.current = now;
  const start = now - HISTORY_SECONDS;
  const at = Math.max(start, Math.min(now, value ?? now));

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => {
      setReducedMotion(media.matches);
      if (media.matches) setPlaying(false);
    };
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (!playing) return;
    let frame: number;
    let previous = performance.now();
    const animate = (time: number) => {
      if (time - previous >= 32) {
        const next = (cursor.current ?? end.current - HISTORY_SECONDS)
          + (time - previous) * HISTORY_SECONDS / 30000;
        previous = time;
        if (next >= end.current) {
          onChange(null);
          setPlaying(false);
          return;
        }
        cursor.current = next;
        onChange(next);
      }
      frame = requestAnimationFrame(animate);
    };
    const pauseWhenHidden = () => { if (document.hidden) setPlaying(false); };
    frame = requestAnimationFrame(animate);
    document.addEventListener('visibilitychange', pauseWhenHidden);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('visibilitychange', pauseWhenHidden);
    };
  }, [playing, onChange]);

  const seek = (next: number) => {
    setPlaying(false);
    onChange(next >= now ? null : Math.max(start, next));
  };

  const label = value === null ? 'Live' : dateLabel(at);

  return (
    <section className="job-timeline" aria-label="Opening history">
      <button
        className="timeline-play"
        aria-label={playing ? 'Pause timeline' : 'Play timeline'}
        disabled={loading || reducedMotion}
        title={reducedMotion ? 'Playback is off for reduced motion; use the slider' : 'Replay the last 30 days'}
        onClick={() => {
          if (!playing && value === null) onChange(start);
          setPlaying(!playing);
        }}
      >
        {playing ? <Pause size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
      </button>
      <span className="timeline-label">
        <strong>{label}</strong>
        <span className="timeline-count" title={truncated ? 'History is limited to 4,000 jobs' : undefined}>
          {loading ? 'Loading...' : `${count} open${truncated ? ' (limited)' : ''}`}
        </span>
      </span>
      <div className="timeline-track" style={{ '--timeline-progress': `${((at - start) / HISTORY_SECONDS) * 100}%` } as CSSProperties}>
        <input
          type="range"
          aria-label="Opening history time"
          aria-valuetext={`${label}, ${count} open${truncated ? ', history limited to 4,000 jobs' : ''}`}
          min={start}
          max={now}
          step="any"
          value={at}
          disabled={loading}
          onKeyDown={(event) => {
            const target = event.key === 'Home' ? start : event.key === 'End' ? now
              : event.key === 'ArrowLeft' || event.key === 'ArrowDown' ? at - 3600
              : event.key === 'ArrowRight' || event.key === 'ArrowUp' ? at + 3600
              : event.key === 'PageDown' ? at - 86400 : event.key === 'PageUp' ? at + 86400 : null;
            if (target !== null) {
              event.preventDefault();
              seek(target);
            }
          }}
          onChange={(event) => seek(Number(event.target.value))}
        />
      </div>
      <button
        className={`timeline-live ${value === null ? 'is-live' : ''}`}
        onClick={() => seek(now)}
        aria-pressed={value === null}
        disabled={loading}
      >
        <Radio size={14} aria-hidden="true" /> Live
      </button>
    </section>
  );
}
