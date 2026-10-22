import { useState, useMemo, useEffect, useRef, memo, type CSSProperties } from 'react';
import { Presence } from '@/components/ui/presence';
import {
  List,
  Grid2X2,
  ChevronDown,
  ChevronUp,
  MapPin,
  Sparkles,
  ArrowRight,
  Bookmark,
  Check,
  Columns2,
  X,
} from 'lucide-react';
import { type Job } from '@/lib/jobs';
import { CompanyMark, MatchMatrix } from './match-matrix';

export interface MapExploreDrawerProps {
  jobs: Job[];
  selectedId: string | null;
  onSelectJob: (id: string) => void;
  onHoverJob: (id: string | null) => void;
  saved: string[];
  onToggleSave: (id: string) => void;
  comparing: string[];
  onToggleCompare: (id: string) => void;
  isNew: (job: Job) => boolean;
  onResetFilters: () => void;
}

export const MapExploreDrawer = memo(function MapExploreDrawer({
  jobs,
  selectedId,
  onSelectJob,
  onHoverJob,
  saved,
  onToggleSave,
  comparing,
  onToggleCompare,
  isNew,
  onResetFilters,
}: MapExploreDrawerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards');
  const [sortBy, setSortBy] = useState<'match' | 'recent'>('match');
  const [visibleCount, setVisibleCount] = useState(24);
  const loaderRef = useRef<HTMLDivElement>(null);

  const sortedJobs = useMemo(() => {
    return [...jobs].sort((a, b) => {
      if (sortBy === 'recent') {
        return a.daysAgo - b.daysAgo || b.score - a.score;
      }
      return b.score - a.score;
    });
  }, [jobs, sortBy]);

  // Reset lazy load slice when jobs or sort/view changes
  useEffect(() => {
    setVisibleCount(24);
  }, [jobs.length, sortBy, viewMode]);

  // Infinite scroll trigger via IntersectionObserver
  useEffect(() => {
    if (!isOpen || viewMode !== 'cards' || visibleCount >= sortedJobs.length) return;
    const target = loaderRef.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setVisibleCount((prev) => Math.min(prev + 24, sortedJobs.length));
        }
      },
      { root: null, rootMargin: '300px' }
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [isOpen, viewMode, visibleCount, sortedJobs.length]);

  const visibleCards = useMemo(() => {
    return sortedJobs.slice(0, visibleCount);
  }, [sortedJobs, visibleCount]);

  return (
    <>
      {/* Floating Bottom Explore Pill Trigger (Google Maps style) */}
      {!isOpen && (
        <div className="gmap-explore-trigger-wrap gmap-ui-floating motion-trigger">
          <button
            className="gmap-explore-pill-btn"
            onClick={() => setIsOpen(true)}
            title="Explore matching opportunities list"
          >
            <List size={15} className="text-primary flex-shrink-0" />
            <span className="font-semibold whitespace-nowrap">Explore Results</span>
            <span className="explore-pill-count flex-shrink-0">{jobs.length.toLocaleString()}</span>
            <ChevronUp size={14} className="opacity-70 flex-shrink-0" />
          </button>
        </div>
      )}

      {/* Slide-Up Bottom Drawer with Backdrop */}
      <Presence show={isOpen} exitMs={340}>
        {(st) => (
        <>
          <div
            className="gmap-bottom-sheet-backdrop motion-backdrop"
            data-state={st}
            onClick={() => setIsOpen(false)}
            title="Click to dismiss drawer"
          />
          <div className="gmap-bottom-sheet gmap-ui-floating motion-sheet" data-state={st}>
            {/* Drawer Handle & Header */}
            <div className="sheet-handle-row" onClick={() => setIsOpen(false)}>
              <div className="sheet-drag-handle" />
            </div>

            <div className="sheet-header">
              <div className="sheet-header-main">
                <div className="sheet-title-group">
                  <h3 className="sheet-title">Matching Opportunities</h3>
                  <span className="sheet-count-tag">
                    {jobs.length.toLocaleString()} roles
                  </span>
                </div>

                {/* Mobile-only close button in header top-right */}
                <button
                  className="sheet-close-btn mobile-only"
                  onClick={() => setIsOpen(false)}
                  title="Collapse drawer"
                  aria-label="Collapse drawer"
                >
                  <ChevronDown size={18} />
                </button>
              </div>

              <div className="sheet-controls">
                {/* Sort Switcher */}
                <div className="sheet-sort-group" role="tablist">
                  <button
                    className={`sort-btn ${sortBy === 'match' ? 'active' : ''}`}
                    onClick={() => setSortBy('match')}
                    role="tab"
                    aria-selected={sortBy === 'match'}
                  >
                    <span>Top Match</span>
                  </button>
                  <button
                    className={`sort-btn ${sortBy === 'recent' ? 'active' : ''}`}
                    onClick={() => setSortBy('recent')}
                    role="tab"
                    aria-selected={sortBy === 'recent'}
                  >
                    <span>Most Recent</span>
                  </button>
                </div>

                {/* View Mode Toggle */}
                <div className="sheet-view-toggle">
                  <button
                    className={`view-btn ${viewMode === 'cards' ? 'active' : ''}`}
                    onClick={() => setViewMode('cards')}
                    title="Card View"
                    aria-label="Card View"
                  >
                    <List size={14} />
                  </button>
                  <button
                    className={`view-btn ${viewMode === 'table' ? 'active' : ''}`}
                    onClick={() => setViewMode('table')}
                    title="Heatmap Table"
                    aria-label="Heatmap Table"
                  >
                    <Grid2X2 size={14} />
                  </button>
                </div>

                {/* Desktop-only close button */}
                <button
                  className="sheet-close-btn desktop-only"
                  onClick={() => setIsOpen(false)}
                  title="Collapse drawer"
                  aria-label="Collapse drawer"
                >
                  <ChevronDown size={18} />
                </button>
              </div>
            </div>

            {/* Drawer Content */}
            <div className="sheet-content-scroll">
              {jobs.length === 0 ? (
                <div className="sheet-empty">
                  <p>No opportunities match your active filters.</p>
                  <button className="empty-reset-btn" onClick={onResetFilters}>
                    Reset All Filters
                  </button>
                </div>
              ) : viewMode === 'cards' ? (
                <div className="sheet-cards-grid">
                  {visibleCards.map((job, idx) => {
                    const isSaved = saved.includes(job.id);
                    const isComparing = comparing.includes(job.id);
                    const isSelected = selectedId === job.id;
                    const recent = isNew(job);

                    return (
                      <div
                        key={job.id}
                        className={`sheet-job-card motion-rise ${isSelected ? 'selected' : ''}`}
                        style={{ '--i': idx % 12 } as CSSProperties}
                        onClick={() => {
                          onSelectJob(job.id);
                          setIsOpen(false);
                        }}
                        onMouseEnter={() => onHoverJob(job.id)}
                        onMouseLeave={() => onHoverJob(null)}
                      >
                        <div className="card-top">
                          <CompanyMark job={job} />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5">
                              <span className="card-company-name truncate">{job.company}</span>
                              {recent && <span className="card-new-tag">NEW</span>}
                            </div>
                            <span className="card-source-tag">{job.source}</span>
                          </div>
                          <div className="card-score-badge">
                            <span>{job.score}%</span>
                          </div>
                        </div>

                        <h4 className="card-job-title">{job.title}</h4>

                        <div className="card-meta-line">
                          <MapPin size={11} className="inline mr-1" />
                          <span>{job.location}</span>
                          <span className="mx-1">·</span>
                          <span>{job.seniority}</span>
                        </div>

                        <div className="card-bottom-actions" onClick={(e) => e.stopPropagation()}>
                          <button
                            className={`card-action-icon ${isSaved ? 'active' : ''}`}
                            onClick={() => onToggleSave(job.id)}
                            title={isSaved ? 'Shortlisted' : 'Shortlist'}
                          >
                            {isSaved ? <Check size={13} /> : <Bookmark size={13} />}
                          </button>
                          <button
                            className={`card-action-icon ${isComparing ? 'active' : ''}`}
                            onClick={() => onToggleCompare(job.id)}
                            title="Compare"
                          >
                            <Columns2 size={13} />
                          </button>
                          <button
                            className="card-inspect-btn"
                            onClick={() => {
                              onSelectJob(job.id);
                              setIsOpen(false);
                            }}
                          >
                            View on Map <ArrowRight size={11} />
                          </button>
                        </div>
                      </div>
                    );
                  })}

                  {/* Lazy Load Sentinel & Manual Load More Button */}
                  {visibleCount < sortedJobs.length && (
                    <div ref={loaderRef} className="sheet-load-more">
                      <button
                        className="sheet-load-more-btn"
                        onClick={() => setVisibleCount((prev) => Math.min(prev + 24, sortedJobs.length))}
                      >
                        Load More Opportunities ({visibleCount} of {sortedJobs.length.toLocaleString()})
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="sheet-table-wrap">
                  <MatchMatrix
                    jobs={sortedJobs}
                    selectedId={selectedId || undefined}
                    onSelect={(id) => {
                      onSelectJob(id);
                      setIsOpen(false);
                    }}
                    reset={onResetFilters}
                  />
                </div>
              )}
            </div>
          </div>
        </>
        )}
      </Presence>
    </>
  );
});
