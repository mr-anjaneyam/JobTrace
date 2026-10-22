import { Columns2, Radio, Sparkles } from 'lucide-react';

export interface MapStatusPillProps {
  totalCount: number;
  sweetCount: number;
  shortlistCount: number;
  compareCount: number;
  onOpenCompare: () => void;
  isScanning: boolean;
  scanStatus: string | null;
}

export function MapStatusPill({
  totalCount,
  sweetCount,
  shortlistCount,
  compareCount,
  onOpenCompare,
  isScanning,
  scanStatus,
}: MapStatusPillProps) {
  return (
    <div className="gmap-status-cluster gmap-ui-floating">
      {/* Compare Floating Pill if compare items selected */}
      {compareCount > 0 && (
        <button
          className="gmap-compare-pill motion-trigger-soft"
          onClick={onOpenCompare}
          title="Open Side-by-Side Comparison"
        >
          <Columns2 size={13} className="text-primary" />
          <span>Compare Roles</span>
          <span className="compare-pill-badge">{compareCount}/2</span>
        </button>
      )}

      {/* Main Radar Status Badge */}
      <div className="gmap-radar-status-badge">
        <span className={`radar-pulse-dot ${isScanning ? 'scanning' : ''}`} />
        <span className="status-label">
          {isScanning ? (
            <span className="flex items-center gap-1.5 text-primary">
              <Sparkles size={11} className="animate-spin" />
              {scanStatus || 'Radar scanning…'}
            </span>
          ) : (
            <>
              <strong>JobTrace Live</strong>
              <span className="status-separator">·</span>
              <span>{totalCount} Active</span>
              <span className="status-separator">·</span>
              <span className="text-emerald-600 font-medium">{sweetCount} Prime Fit</span>
            </>
          )}
        </span>
      </div>
    </div>
  );
}
