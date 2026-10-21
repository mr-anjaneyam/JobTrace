import { useState } from 'react';
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
import { MiniRadar } from './mini-radar';

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

export function MapExploreDrawer({
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

  const sortedJobs = [...jobs].sort((a, b) => {
    if (sortBy === 'recent') {
      return a.daysAgo - b.daysAgo || b.score - a.score;
    }
    return b.score - a.score;
  });

  return (
    <>
      {/* Floating Bottom Explore Pill Trigger (Google Maps style) */}
      {!isOpen && (
        <div className="gmap-explore-trigger-wrap gmap-ui-floating">
          <button
            className="gmap-explore-pill-btn"
            onClick={() => setIsOpen(true)}
            title="Explore matching opportunities list"
          >
            <List size={15} className="text-primary" />
            <span className="font-medium">Explore Results</span>
            <span className="explore-pill-count">{jobs.length}</span>
            <ChevronUp size={14} className="opacity-70" />
          </button>
        </div>
      )}

      {/* Slide-Up Bottom Drawer with Backdrop */}
      {isOpen && (
        <>
          <div
            className="gmap-bottom-sheet-backdrop animate-fade-in"
            onClick={() => setIsOpen(false)}
            title="Click to dismiss drawer"
          />
          <div className="gmap-bottom-sheet gmap-ui-floating animate-slide-up">
            {/* Drawer Handle & Header */}
            <div className="sheet-handle-row" onClick={() => setIsOpen(false)}>
              <div className="sheet-drag-handle" />
            </div>

          <div className="sheet-header">
            <div className="flex items-center gap-3">
              <h3 className="sheet-title">Matching Opportunities</h3>
              <span className="sheet-count-tag">{jobs.length} roles</span>
            </div>

            <div className="sheet-controls">
              {/* Sort Switcher */}
              <div className="sheet-sort-group">
                <button
                  className={`sort-btn ${sortBy === 'match' ? 'active' : ''}`}
                  onClick={() => setSortBy('match')}
                >
                  Top Match
                </button>
                <button
                  className={`sort-btn ${sortBy === 'recent' ? 'active' : ''}`}
                  onClick={() => setSortBy('recent')}
                >
                  Most Recent
                </button>
              </div>

              {/* View Mode Toggle */}
              <div className="sheet-view-toggle">
                <button
                  className={`view-btn ${viewMode === 'cards' ? 'active' : ''}`}
                  onClick={() => setViewMode('cards')}
                  title="Card View"
                >
                  <List size={13} />
                </button>
                <button
                  className={`view-btn ${viewMode === 'table' ? 'active' : ''}`}
                  onClick={() => setViewMode('table')}
                  title="Heatmap Table"
                >
                  <Grid2X2 size={13} />
                </button>
              </div>

              {/* Minimize / Close Button */}
              <button
                className="sheet-close-btn"
                onClick={() => setIsOpen(false)}
                title="Collapse list"
              >
                <ChevronDown size={16} />
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
                {sortedJobs.map((job) => {
                  const isSaved = saved.includes(job.id);
                  const isComparing = comparing.includes(job.id);
                  const isSelected = selectedId === job.id;
                  const recent = isNew(job);

                  return (
                    <div
                      key={job.id}
                      className={`sheet-job-card ${isSelected ? 'selected' : ''}`}
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
  </>
);
}
