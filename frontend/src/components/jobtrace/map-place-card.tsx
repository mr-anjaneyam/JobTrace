import { Suspense, lazy, useEffect, useState, type CSSProperties } from 'react';
import {
  X,
  ArrowLeft,
  MapPin,
  ExternalLink,
  Bookmark,
  Check,
  Columns2,
  Share2,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Clock3,
  Building2,
  CheckCircle2,
  Trash2,
  AlertTriangle,
  Loader2,
} from 'lucide-react';
import { dimensions, type Job } from '@/lib/jobs';
import { api } from '@/lib/api';
import { formatJobDescription } from '@/lib/utils';
import { CompanyMark } from './match-matrix';
const MiniRadar = lazy(() => import('./mini-radar').then((m) => ({ default: m.MiniRadar })));

export interface MapPlaceCardProps {
  job: Job | null;
  onClose: () => void;
  saved: boolean;
  onToggleSave: (id: string) => void;
  isComparing: boolean;
  onToggleCompare: (id: string) => void;
  onDiscard?: (id: string) => void;
  state?: 'open' | 'closed';
}

export function MapPlaceCard({
  job,
  onClose,
  saved,
  onToggleSave,
  isComparing,
  onToggleCompare,
  onDiscard,
  state = 'open',
}: MapPlaceCardProps) {
  const [expandedDesc, setExpandedDesc] = useState(false);
  const [copied, setCopied] = useState(false);
  const [fullDesc, setFullDesc] = useState<string | null>(null);
  const [liveness, setLiveness] = useState<{
    status: 'idle' | 'checking' | 'active' | 'archived';
    reason?: string;
  }>({ status: 'idle' });
  const [discarding, setDiscarding] = useState(false);

  useEffect(() => {
    setFullDesc(null);
    setExpandedDesc(false);
    setCopied(false);

    if (!job?.id) {
      setLiveness({ status: 'idle' });
      return;
    }

    let isMounted = true;
    setLiveness({ status: 'checking', reason: 'Checking listing availability...' });

    api.verifyJob(job.id)
      .then((res) => {
        if (!isMounted) return;
        if (res.active) {
          setLiveness({ status: 'active', reason: res.reason || 'Verified active on board' });
        } else {
          setLiveness({ status: 'archived', reason: res.reason || 'Listing has been archived or closed' });
        }
      })
      .catch(() => {
        if (!isMounted) return;
        setLiveness({ status: 'idle' });
      });

    return () => {
      isMounted = false;
    };
  }, [job?.id]);

  useEffect(() => {
    if (expandedDesc && job && !fullDesc) {
      api.getJobDetail(job.id)
        .then((detail) => {
          if (detail.description) setFullDesc(detail.description);
        })
        .catch(() => {});
    }
  }, [expandedDesc, job?.id, fullDesc]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!job) return null;

  const handleShare = () => {
    if (job.url && job.url !== '#') {
      navigator.clipboard.writeText(job.url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDiscard = async () => {
    if (!job) return;
    setDiscarding(true);
    try {
      if (onDiscard) {
        onDiscard(job.id);
      } else {
        await api.discardJob(job.id);
        onClose();
      }
    } catch (err) {
      console.error('Failed to discard job:', err);
    } finally {
      setDiscarding(false);
    }
  };

  const scoreDescription =
    job.score >= 85
      ? 'Prime Strategic Fit'
      : job.score >= 70
      ? 'Strong Opportunity'
      : job.score >= 55
      ? 'Promising Fit'
      : 'Stretch / Feasibility Check';

  return (
    <div className="gmap-place-card gmap-ui-floating motion-card" data-state={state}>
      {/* Hero Cover Header */}
      <div key={`cover-${job.id}`} className="place-card-cover animate-fade-in">
        <div className="place-cover-top-bar">
          <button
            className="place-back-btn"
            onClick={onClose}
            title="Back to search (Esc)"
            aria-label="Back to search"
          >
            <ArrowLeft size={16} />
            <span className="text-xs font-medium ml-1">Back</span>
          </button>
          <button
            className="place-close-btn"
            onClick={onClose}
            title="Close details (Esc)"
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="place-header-content">
          <div className="place-logo-wrap">
            <CompanyMark job={job} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h2 className="place-company-name truncate">{job.company}</h2>
              {job.domain && (
                <a
                  href={`https://${job.domain}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="place-domain-link"
                  title={`Visit ${job.domain}`}
                >
                  {job.domain}
                  <ExternalLink size={10} className="inline ml-1" />
                </a>
              )}
            </div>
            <h1 className="place-job-title">{job.title}</h1>
          </div>
        </div>

        {/* Location & Seniority Meta */}
        <div className="place-meta-strip">
          <span className="meta-item">
            <MapPin size={12} className="inline mr-1 text-primary" />
            {job.location}
          </span>
          <span className="meta-dot">·</span>
          <span className="meta-item">{job.seniority} Level</span>
          <span className="meta-dot">·</span>
          <span className="meta-item">
            <Clock3 size={11} className="inline mr-1" />
            {job.daysAgo === 0 ? 'Today' : `${job.daysAgo}d ago`}
          </span>
          <span className="meta-dot">·</span>
          <span className="meta-source-badge">{job.source}</span>
        </div>

        {/* Real-time Listing Verification Banner */}
        {liveness.status === 'checking' && (
          <div className="place-liveness-banner is-checking">
            <span className="flex items-center gap-1.5 font-medium">
              <Loader2 size={12} className="animate-spin text-slate-500" />
              <span>Verifying live posting availability...</span>
            </span>
          </div>
        )}

        {liveness.status === 'active' && (
          <div className="place-liveness-banner is-active">
            <span className="flex items-center gap-1.5 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Live & Open: Accepting Applications</span>
            </span>
          </div>
        )}

        {liveness.status === 'archived' && (
          <div className="place-liveness-banner is-archived">
            <div className="flex items-center gap-1.5 min-w-0">
              <AlertTriangle size={14} className="shrink-0 text-rose-600" />
              <span className="truncate font-medium" title={liveness.reason}>
                {liveness.reason || 'Listing Archived / Closed'}
              </span>
            </div>
            <button
              className="banner-action-btn"
              onClick={handleDiscard}
              disabled={discarding}
              title="Remove this archived posting from your map"
            >
              {discarding ? 'Discarding...' : 'Discard from Map'}
            </button>
          </div>
        )}
      </div>

      {/* Google Maps Place Action Buttons (Executive 2-tier layout) */}
      <div className="place-actions-shell">
        {/* Tier 1: Primary Actions (Apply + Shortlist) */}
        <div className="place-actions-primary">
          {job.url && job.url !== '#' && (
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className={`place-btn-primary ${liveness.status === 'archived' ? 'btn-archived' : ''}`}
              title={liveness.status === 'archived' ? 'Warning: Listing appears archived on provider' : 'Open application URL in new tab'}
            >
              <ExternalLink size={15} />
              <span>{liveness.status === 'archived' ? 'Archived on Provider' : `Apply on ${job.company}`}</span>
            </a>
          )}

          <button
            className={`place-btn-save ${saved ? 'is-saved' : ''}`}
            onClick={() => onToggleSave(job.id)}
            title={saved ? 'Remove from shortlist' : 'Save to shortlist'}
          >
            {saved ? <Check size={15} className="text-emerald-600" /> : <Bookmark size={15} />}
            <span>{saved ? 'Shortlisted' : 'Save'}</span>
          </button>
        </div>

        {/* Tier 2: Utility Toolbar (Compare, Share, Discard) */}
        <div className="place-actions-toolbar">
          <button
            className={`place-btn-tool ${isComparing ? 'is-comparing' : ''}`}
            onClick={() => onToggleCompare(job.id)}
            title={isComparing ? 'Remove from comparison' : 'Compare role against others'}
          >
            <Columns2 size={13} />
            <span>{isComparing ? 'Comparing' : 'Compare'}</span>
          </button>

          <button
            className="place-btn-tool"
            onClick={handleShare}
            title="Copy link to clipboard"
          >
            {copied ? <CheckCircle2 size={13} className="text-emerald-500" /> : <Share2 size={13} />}
            <span>{copied ? 'Copied Link' : 'Share'}</span>
          </button>

          <button
            className="place-btn-tool btn-discard"
            onClick={handleDiscard}
            disabled={discarding}
            title="Discard closed or unwanted job from your matrix"
          >
            <Trash2 size={13} />
            <span>{discarding ? 'Discarding...' : 'Discard'}</span>
          </button>
        </div>
      </div>

      <div key={`body-${job.id}`} className="place-body-scroll animate-fade-in">
        {/* Match Score Hero Card */}
        <div className="place-score-card">
          <div className="score-ring-wrap">
            <div className="gmap-score-ring" style={{ '--score-val': job.score } as CSSProperties}>
              <span className="score-num">{job.score}</span>
              <span className="score-pct">%</span>
            </div>
          </div>
          <div className="score-text-wrap">
            <div className="score-badge-label">{scoreDescription}</div>
            <p className="score-subtext">Overall strategic fit matching your candidate profile</p>
          </div>
        </div>

        {/* 6-Dimensional Mini Radar Chart */}
        <div className="place-radar-section">
          <div className="section-title">
            <span>Profile Match Radar</span>
            <span className="section-sub">6 Strategic Vectors</span>
          </div>
          <div className="place-radar-container">
            <Suspense fallback={<div style={{ height: 220 }} />}>
              <MiniRadar job={job} labels={true} />
            </Suspense>
          </div>

          {/* Breakdown Bars */}
          <div className="place-breakdown-grid">
            {dimensions.map((dim, i) => (
              <div key={dim} className="breakdown-item">
                <div className="breakdown-header">
                  <span className="dim-name">{dim}</span>
                  <span className="dim-val">{job.breakdown[i] ?? 0}%</span>
                </div>
                <div className="breakdown-track">
                  <div
                    className="breakdown-bar"
                    style={{ width: `${job.breakdown[i] ?? 0}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* AI Strategic Assessment Reason */}
        <div className="place-reason-card">
          <div className="reason-header">
            <Sparkles size={14} className="text-primary" />
            <span>AI Strategic Evaluation</span>
          </div>
          <p className="reason-text">{job.reason}</p>
        </div>

        {/* Skills & Tech Stack Tags */}
        {job.tags && job.tags.length > 0 && (
          <div className="place-tags-section">
            <span className="tags-label">Key Stack & Requirements</span>
            <div className="tags-wrap">
              {job.tags.map((t) => (
                <span key={t} className="place-tag">
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Expandable Role Description */}
        <div className="place-desc-section">
          <button
            className="desc-toggle-btn"
            onClick={() => setExpandedDesc(!expandedDesc)}
          >
            <span>Role Description & Details</span>
            {expandedDesc ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>

          {expandedDesc && (
            <div className="desc-content animate-fade-in">
              <p className="whitespace-pre-line leading-relaxed">
                {formatJobDescription(fullDesc || job.description)}
              </p>
              <div className="desc-footer">
                <Building2 size={12} className="inline mr-1" />
                Discovered via {job.source}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
