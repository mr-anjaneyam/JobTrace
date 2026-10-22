import { useEffect, useState } from 'react';
import { AlertTriangle, ArrowRight } from 'lucide-react';
import { api, type OnboardingScan } from '@/lib/api';
import { firstName } from './model';

const TIPS = [
  'Roles that fail your filters are still tracked, so changing a filter never fakes a closure.',
  'Seniority and location caps run as plain code, so they cost zero tokens.',
  'Press Esc in the dashboard to close any card, and click a pin to open it.',
  'You can switch scoring engines any time from Settings.',
];

const PHASES = ['Reading portals', 'Matching to your resume', 'Finishing up'];

export function ProgressScreen({ name, onOpenDashboard }: { name: string; onOpenDashboard: () => void }) {
  const [scan, setScan] = useState<OnboardingScan | null>(null);
  const [offline, setOffline] = useState(false);
  const [tip, setTip] = useState(0);

  const finished = scan?.state === 'done' || scan?.state === 'error';

  useEffect(() => {
    if (finished) return;
    let alive = true;
    const tick = async () => {
      try {
        const status = await api.getOnboardingStatus();
        if (alive) {
          setScan(status.scan);
          setOffline(false);
        }
      } catch {
        if (alive) setOffline(true);
      }
    };
    void tick();
    const timer = setInterval(tick, 1500);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [finished]);

  useEffect(() => {
    const timer = setInterval(() => setTip((t) => (t + 1) % TIPS.length), 7000);
    return () => clearInterval(timer);
  }, []);

  const percent = Math.max(2, Math.min(100, scan?.percent ?? 2));
  const phase = percent < 50 ? 0 : percent < 98 ? 1 : 2;
  const who = firstName(name);

  if (scan?.state === 'done') {
    return (
      <div className="ob-progress ob-progress-done">
        <svg className="ob-check" viewBox="0 0 52 52" aria-hidden="true">
          <circle cx="26" cy="26" r="24" />
          <path d="M15 27.5l7 7L37 19" />
        </svg>
        <h1>{who ? `You're all set, ${who}.` : "You're all set."}</h1>
        <p className="ob-progress-sub">
          Found <strong>{scan.new}</strong> new {scan.new === 1 ? 'role' : 'roles'}
          {scan.scored > 0 ? <> and scored <strong>{scan.scored}</strong></> : null}. Your dashboard is ready.
        </p>
        {scan.note && <div className="ob-note">{scan.note}</div>}
        <button type="button" className="ob-btn ob-btn-primary ob-btn-lg" onClick={onOpenDashboard} autoFocus>
          Open dashboard <ArrowRight size={16} />
        </button>
      </div>
    );
  }

  if (scan?.state === 'error') {
    return (
      <div className="ob-progress">
        <span className="ob-warn">
          <AlertTriangle size={22} />
        </span>
        <h1>The first scan hit a snag</h1>
        <p className="ob-progress-sub">{scan.message || 'Something went wrong while reading career pages.'}</p>
        <p className="ob-progress-sub">Your settings are saved. You can retry from the dashboard with the scan button.</p>
        <button type="button" className="ob-btn ob-btn-primary ob-btn-lg" onClick={onOpenDashboard}>
          Open dashboard <ArrowRight size={16} />
        </button>
      </div>
    );
  }

  return (
    <div className="ob-progress">
      <div className="ob-orb" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <h1>{who ? `Building your radar, ${who}` : 'Building your radar'}</h1>
      <p className="ob-progress-sub">
        We&apos;re reading career pages and scoring openings in the background. <strong>Come back in a few minutes.</strong>{' '}
        You can close this tab; JobTrace keeps working as long as it is running.
      </p>

      <div className="ob-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label="Scan progress">
        <div className="ob-bar-fill" style={{ transform: `scaleX(${percent / 100})` }} />
      </div>
      <div className="ob-bar-meta">
        <span key={scan?.message} className="ob-status">
          {offline ? 'Reconnecting…' : scan?.message || 'Warming up'}
        </span>
        <span className="ob-percent">{percent}%</span>
      </div>

      <ol className="ob-phases">
        {PHASES.map((label, i) => (
          <li key={label} className={i < phase ? 'is-done' : i === phase ? 'is-active' : ''}>
            <span />
            {label}
          </li>
        ))}
      </ol>

      <p key={tip} className="ob-tip">
        {TIPS[tip]}
      </p>

      <button type="button" className="ob-link ob-skip" onClick={onOpenDashboard}>
        Open the dashboard while this finishes
      </button>
    </div>
  );
}
