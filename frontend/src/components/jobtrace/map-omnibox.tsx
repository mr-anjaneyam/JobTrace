import { useState, useRef, useEffect, type FormEvent } from 'react';
import {
  Search,
  X,
  Compass,
  Settings,
  User,
  RefreshCw,
  Sparkles,
  Bookmark,
  ChevronDown,
  Filter,
  Check,
  ShieldCheck,
} from 'lucide-react';

export interface MapOmniboxProps {
  searchQuery: string;
  onSearchChange: (q: string) => void;
  shortlistOnly: boolean;
  onToggleShortlist: () => void;
  shortlistCount: number;
  seniority: string;
  onSeniorityChange: (s: string) => void;
  location: string;
  onLocationChange: (loc: string) => void;
  source: string;
  onSourceChange: (src: string) => void;
  sources: string[];
  minimumScore: number;
  onMinimumScoreChange: (score: number) => void;
  selectedQuadrant: 'all' | 'sweet' | 'stretch' | 'safety';
  onQuadrantChange: (quad: 'all' | 'sweet' | 'stretch' | 'safety') => void;
  isScanning: boolean;
  scanStatus: string | null;
  onTriggerScan: () => void;
  onOpenProfile: () => void;
  onOpenSettings: () => void;
  onResetFilters: () => void;
  activeFilterCount: number;
  onPurgeClosed?: () => Promise<any>;
}

export function MapOmnibox({
  searchQuery,
  onSearchChange,
  shortlistOnly,
  onToggleShortlist,
  shortlistCount,
  seniority,
  onSeniorityChange,
  location,
  onLocationChange,
  source,
  onSourceChange,
  sources,
  minimumScore,
  onMinimumScoreChange,
  selectedQuadrant,
  onQuadrantChange,
  isScanning,
  scanStatus,
  onTriggerScan,
  onOpenProfile,
  onOpenSettings,
  onResetFilters,
  activeFilterCount,
  onPurgeClosed,
}: MapOmniboxProps) {
  const [seniorityOpen, setSeniorityOpen] = useState(false);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [filterMenuOpen, setFilterMenuOpen] = useState(false);
  const [isPurging, setIsPurging] = useState(false);
  const [purgeResult, setPurgeResult] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const seniorityBtnRef = useRef<HTMLButtonElement>(null);
  const sourceBtnRef = useRef<HTMLButtonElement>(null);

  const handleCleanArchived = async () => {
    if (!onPurgeClosed || isPurging) return;
    setIsPurging(true);
    setPurgeResult(null);
    try {
      const res = await onPurgeClosed();
      if (res && res.total_closed > 0) {
        setPurgeResult(`Purged ${res.total_closed}`);
      } else {
        setPurgeResult('All Active');
      }
      setTimeout(() => setPurgeResult(null), 3000);
    } catch (err) {
      console.error('Error purging closed:', err);
    } finally {
      setIsPurging(false);
    }
  };

  useEffect(() => {
    const handleOutsideClick = (e: globalThis.MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setSeniorityOpen(false);
        setSourceOpen(false);
        setFilterMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  return (
    <div ref={containerRef} className="gmap-omnibox-shell gmap-ui-floating">
      {/* Primary Google Maps Floating Search Card */}
      <div className="gmap-omnibox-card">
        {/* Brand Compass / Icon */}
        <div className="omnibox-logo-btn" title="JobRadar Map Navigation">
          <Compass size={20} className={isScanning ? 'animate-spin text-primary' : 'text-primary'} />
        </div>

        {/* Search Input */}
        <div className="omnibox-input-wrap">
          <input
            type="text"
            className="omnibox-input"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search roles, companies, tech stack..."
            aria-label="Search opportunities"
          />
          {searchQuery && (
            <button
              className="omnibox-clear-btn"
              onClick={() => onSearchChange('')}
              title="Clear search"
            >
              <X size={15} />
            </button>
          )}
        </div>

        {/* Divider */}
        <div className="omnibox-v-divider" />

        {/* Action Icon: Trigger Radar Scan */}
        <button
          className={`omnibox-action-btn ${isScanning ? 'btn-scanning' : ''}`}
          onClick={onTriggerScan}
          disabled={isScanning}
          title={isScanning ? (scanStatus || 'Radar scan running...') : 'Trigger live portal scan'}
        >
          <RefreshCw size={17} className={isScanning ? 'animate-spin text-primary' : ''} />
        </button>

        {/* Action Icon: Candidate Profile & Resume */}
        <button
          className="omnibox-action-btn"
          onClick={onOpenProfile}
          title="Candidate Profile & Resume upload"
        >
          <User size={17} />
        </button>

        {/* Action Icon: Settings Dialog */}
        <button
          className="omnibox-action-btn"
          onClick={onOpenSettings}
          title="Settings (LLM & Telegram bot)"
        >
          <Settings size={17} />
        </button>
      </div>

      {/* Streaming Live Scan Status Banner if active */}
      {scanStatus && (
        <div className="gmap-scan-banner animate-pulse">
          <Sparkles size={13} className="text-primary" />
          <span className="truncate">{scanStatus}</span>
        </div>
      )}

      {/* Google Maps Horizontal Category Chips Row */}
      <div className="gmap-chip-rail">
        {/* Shortlist Filter Chip */}
        <button
          className={`gmap-chip ${shortlistOnly ? 'chip-active' : ''}`}
          onClick={onToggleShortlist}
        >
          <Bookmark size={12} className={shortlistOnly ? 'fill-current' : ''} />
          <span>Shortlisted</span>
          {shortlistCount > 0 && <span className="chip-count">{shortlistCount}</span>}
        </button>

        {/* Prime Sector / Sweet Spot Chip */}
        <button
          className={`gmap-chip ${selectedQuadrant === 'sweet' ? 'chip-active chip-sweet' : ''}`}
          onClick={() => onQuadrantChange(selectedQuadrant === 'sweet' ? 'all' : 'sweet')}
        >
          <span className="chip-dot dot-sweet" />
          <span>Sweet Spot</span>
        </button>

        {/* Stretch Reach Chip */}
        <button
          className={`gmap-chip ${selectedQuadrant === 'stretch' ? 'chip-active chip-stretch' : ''}`}
          onClick={() => onQuadrantChange(selectedQuadrant === 'stretch' ? 'all' : 'stretch')}
        >
          <span className="chip-dot dot-stretch" />
          <span>Stretch</span>
        </button>

        {/* Safety Harbor Chip */}
        <button
          className={`gmap-chip ${selectedQuadrant === 'safety' ? 'chip-active chip-safety' : ''}`}
          onClick={() => onQuadrantChange(selectedQuadrant === 'safety' ? 'all' : 'safety')}
        >
          <span className="chip-dot dot-safety" />
          <span>Safety</span>
        </button>

        {/* High Match Score (85%+) Chip */}
        <button
          className={`gmap-chip ${minimumScore >= 85 ? 'chip-active' : ''}`}
          onClick={() => onMinimumScoreChange(minimumScore >= 85 ? 0 : 85)}
        >
          <span>Prime 85%+</span>
        </button>

        {/* Remote Roles Only Chip */}
        <button
          className={`gmap-chip ${location === 'remote' ? 'chip-active' : ''}`}
          onClick={() => onLocationChange(location === 'remote' ? 'all' : 'remote')}
        >
          <span>Remote</span>
        </button>

        {/* Seniority Dropdown Chip */}
        <button
          ref={seniorityBtnRef}
          className={`gmap-chip ${seniority !== 'all' ? 'chip-active' : ''}`}
          onClick={() => {
            setSeniorityOpen(!seniorityOpen);
            setSourceOpen(false);
          }}
        >
          <span>{seniority === 'all' ? 'Seniority' : seniority}</span>
          <ChevronDown size={11} />
        </button>

        {/* Source Dropdown Chip */}
        {sources.length > 0 && (
          <button
            ref={sourceBtnRef}
            className={`gmap-chip ${source !== 'all' ? 'chip-active' : ''}`}
            onClick={() => {
              setSourceOpen(!sourceOpen);
              setSeniorityOpen(false);
            }}
          >
            <span>{source === 'all' ? 'Source' : source}</span>
            <ChevronDown size={11} />
          </button>
        )}

        {/* Clean Stale / Archived Jobs Chip */}
        {onPurgeClosed && (
          <button
            className={`gmap-chip ${isPurging ? 'chip-active' : ''}`}
            onClick={handleCleanArchived}
            disabled={isPurging}
            title="Scan & purge archived or elapsed listings"
          >
            {isPurging ? (
              <RefreshCw size={11} className="animate-spin text-rose-500" />
            ) : (
              <ShieldCheck size={11} className="text-emerald-500" />
            )}
            <span>{purgeResult ? purgeResult : isPurging ? 'Purging...' : 'Clean Stale'}</span>
          </button>
        )}

        {/* Reset All Filters Chip */}
        {activeFilterCount > 0 && (
          <button className="gmap-chip chip-reset" onClick={onResetFilters}>
            <X size={11} />
            <span>Reset ({activeFilterCount})</span>
          </button>
        )}
      </div>

      {/* Floating Dropdown Menus positioned cleanly outside the scrolling rail directly under their chip */}
      {seniorityOpen && (
        <div
          className="gmap-floating-dropdown seniority-dropdown animate-fade-in"
          style={{
            left: seniorityBtnRef.current ? `${seniorityBtnRef.current.offsetLeft}px` : undefined,
          }}
        >
          <div className="dropdown-header-title">Select Seniority Level</div>
          {['all', 'Junior', 'Mid', 'Senior'].map((lvl) => (
            <button
              key={lvl}
              className={`dropdown-option ${seniority === lvl ? 'selected' : ''}`}
              onClick={() => {
                onSeniorityChange(lvl);
                setSeniorityOpen(false);
              }}
            >
              <span>{lvl === 'all' ? 'All Seniority Levels' : lvl}</span>
              {seniority === lvl && <Check size={12} />}
            </button>
          ))}
        </div>
      )}

      {sourceOpen && (
        <div
          className="gmap-floating-dropdown source-dropdown animate-fade-in"
          style={{
            left: sourceBtnRef.current ? `${sourceBtnRef.current.offsetLeft}px` : undefined,
          }}
        >
          <div className="dropdown-header-title">Select Job Portal / Board</div>
          {['all', ...sources].map((s) => (
            <button
              key={s}
              className={`dropdown-option ${source === s ? 'selected' : ''}`}
              onClick={() => {
                onSourceChange(s);
                setSourceOpen(false);
              }}
            >
              <span>{s === 'all' ? 'All Sources' : s}</span>
              {source === s && <Check size={12} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
