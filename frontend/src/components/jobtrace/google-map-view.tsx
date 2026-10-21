import { memo, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent } from 'react';
import {
  Minus,
  Plus,
  Crosshair,
  Layers,
  Sparkles,
  SlidersHorizontal,
  Maximize2,
  Minimize2,
  Tags,
  X,
} from 'lucide-react';
import { TransformWrapper, TransformComponent, type ReactZoomPanPinchRef } from 'react-zoom-pan-pinch';
import { mapAxes, mapQuadrant, positionMarkers, type Job, type MapAxis } from '@/lib/jobs';
import { CompanyMark } from './match-matrix';

export type MapStyleMode = 'carto' | 'satellite' | 'heatmap';

export interface GoogleMapViewProps {
  jobs: Job[];
  selectedId: string | null;
  hoveredId: string | null;
  onSelectJob: (id: string) => void;
  onHoverJob: (id: string | null) => void;
  isNew: (job: Job) => boolean;
  xAxis: MapAxis;
  yAxis: MapAxis;
  threshold: number;
  onAxesChange: (xAxis: MapAxis, yAxis: MapAxis) => void;
  onThresholdChange: (threshold: number) => void;
}

interface MapPinMarkerProps {
  marker: {
    job: Job;
    px: number;
    py: number;
    trueX: number;
    trueY: number;
    x: number;
    y: number;
  };
  isSelected: boolean;
  isHovered: boolean;
  isSweet: boolean;
  quad: string;
  recent: boolean;
  onSelect: (id: string) => void;
  onHover: (marker: { job: Job; px: number; py: number; x: number; y: number } | null) => void;
}

const MapPinMarker = memo(function MapPinMarker({
  marker,
  isSelected,
  isHovered,
  isSweet,
  quad,
  recent,
  onSelect,
  onHover,
}: MapPinMarkerProps) {
  const { job, px, py, x, y } = marker;

  const handleClick = (e: MouseEvent) => {
    e.stopPropagation();
    onSelect(job.id);
  };

  const handleMouseEnter = () => {
    onHover({ job, px, py, x, y });
  };

  const handleMouseLeave = () => {
    onHover(null);
  };

  return (
    <div
      className={`gmap-pin quad-${quad} ${isSelected ? 'pin-selected' : ''} ${isHovered ? 'pin-hovered' : ''} ${isSweet ? 'pin-sweet' : ''}`}
      style={{
        left: `${px}px`,
        top: `${py}px`,
        transform: `translate(-50%, -50%) scale(calc(var(--pin-scale, 1) * ${isSelected ? 1.22 : isHovered ? 1.15 : 1}))`,
      }}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      role="button"
      tabIndex={0}
      aria-label={`${job.company} - ${job.title}`}
    >
      {/* Google Maps Pin Teardrop/Disc Body */}
      <div className="pin-body">
        <CompanyMark job={job} />
        {recent && <span className="pin-new-badge" title="Discovered recently" />}
      </div>

      {/* Match Score Badge on Pin */}
      <span className="pin-score-badge">{job.score}%</span>

      {/* Pin Street/Company Label */}
      <div className="pin-label">
        <span className="pin-company-name">{job.company}</span>
        <span className="pin-job-title">{job.title}</span>
      </div>
    </div>
  );
});

export function GoogleMapView({
  jobs,
  selectedId,
  hoveredId,
  onSelectJob,
  onHoverJob,
  isNew,
  xAxis,
  yAxis,
  threshold,
  onAxesChange,
  onThresholdChange,
}: GoogleMapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const transformRef = useRef<ReactZoomPanPinchRef>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  const [dimensions, setDimensions] = useState({ width: 1400, height: 900 });
  const [mapStyle, setMapStyle] = useState<MapStyleMode>('carto');
  const [showLabels, setShowLabels] = useState(true);
  const [showAxesMenu, setShowAxesMenu] = useState(false);
  const [showLayerMenu, setShowLayerMenu] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [tooltipJob, setTooltipJob] = useState<{ job: Job; px: number; py: number; x: number; y: number } | null>(null);

  const isDraggingRef = useRef(false);
  const dragStartPos = useRef<{ x: number; y: number } | null>(null);
  const rafId = useRef<number | null>(null);
  const lastScaleRef = useRef(1);

  // Directly mutate canvas CSS variable --pin-scale via requestAnimationFrame
  // This eliminates all React re-renders during continuous zoom & pan gestures
  const applyPinScale = useCallback((currentScale: number) => {
    const safeScale =
      typeof currentScale === 'number' && !isNaN(currentScale) && currentScale > 0
        ? currentScale
        : 1;
    if (Math.abs(safeScale - lastScaleRef.current) < 0.0005) return;
    lastScaleRef.current = safeScale;

    if (rafId.current) cancelAnimationFrame(rafId.current);
    rafId.current = requestAnimationFrame(() => {
      if (canvasRef.current) {
        canvasRef.current.style.setProperty('--pin-scale', String(1 / safeScale));
      }
    });
  }, []);

  useEffect(() => {
    if (canvasRef.current) {
      canvasRef.current.style.setProperty('--pin-scale', '1');
    }
    return () => {
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, []);

  // Resize observer to ensure full viewport filling
  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;

    const updateSize = () => {
      const rect = node.getBoundingClientRect();
      setDimensions({
        width: Math.max(800, Math.round(rect.width)),
        height: Math.max(600, Math.round(rect.height)),
      });
    };

    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(node);
    window.addEventListener('resize', updateSize);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', updateSize);
    };
  }, []);

  // Compute positioned markers with collision avoidance
  const markers = useMemo(() => {
    return positionMarkers(jobs, xAxis, yAxis, dimensions.width, dimensions.height);
  }, [jobs, xAxis, yAxis, dimensions.width, dimensions.height]);

  // Only render SVG leader lines for markers that were physically displaced
  const visibleLeaders = useMemo(() => {
    return markers.filter((m) => Math.hypot(m.px - m.trueX, m.py - m.trueY) > 4);
  }, [markers]);

  const xLabel = mapAxes.find((a) => a.value === xAxis)?.label || 'Technical Fit';
  const yLabel = mapAxes.find((a) => a.value === yAxis)?.label || 'Company Relevance';

  // Find marker when hoveredId changes externally
  useEffect(() => {
    if (hoveredId) {
      const m = markers.find((item) => item.job.id === hoveredId);
      if (m) {
        setTooltipJob({ job: m.job, px: m.px, py: m.py, x: m.x, y: m.y });
      }
    } else {
      setTooltipJob(null);
    }
  }, [hoveredId, markers]);

  // Handle Fullscreen Toggle
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  };

  // Recenter / Fit map to bounds
  const handleRecenter = () => {
    if (transformRef.current) {
      transformRef.current.resetTransform(300);
      applyPinScale(1);
    }
  };

  // Pan to selected marker (offsetting center so marker is visible to the right of the 440px place card)
  useEffect(() => {
    if (selectedId && transformRef.current) {
      const target = markers.find((m) => m.job.id === selectedId);
      if (target) {
        const visibleCenterX = (dimensions.width + 440) / 2;
        const visibleCenterY = dimensions.height / 2;
        const targetX = visibleCenterX - target.px;
        const targetY = visibleCenterY - target.py;
        transformRef.current.setTransform(targetX, targetY, 1, 350);
        applyPinScale(1);
      }
    } else if (!selectedId && transformRef.current) {
      transformRef.current.resetTransform(300);
      applyPinScale(1);
    }
  }, [selectedId, dimensions.width, dimensions.height, markers, applyPinScale]);

  // Stable callbacks for memoized pins
  const handleSelectJob = useCallback(
    (id: string) => {
      if (isDraggingRef.current) return;
      onSelectJob(id);
    },
    [onSelectJob]
  );

  const handleHoverMarker = useCallback(
    (marker: { job: Job; px: number; py: number; x: number; y: number } | null) => {
      if (marker) {
        onHoverJob(marker.job.id);
        setTooltipJob(marker);
      } else {
        onHoverJob(null);
        setTooltipJob(null);
      }
    },
    [onHoverJob]
  );

  return (
    <div
      ref={containerRef}
      className={`gmap-viewport ${mapStyle === 'satellite' ? 'theme-satellite' : mapStyle === 'heatmap' ? 'theme-heatmap' : 'theme-carto'}`}
      onClick={() => {
        setShowAxesMenu(false);
        setShowLayerMenu(false);
      }}
    >
      <TransformWrapper
        ref={transformRef}
        minScale={0.7}
        maxScale={4}
        initialScale={1}
        centerOnInit
        smooth
        wheel={{ step: 0.06 }}
        panning={{
          velocityDisabled: true,
          excluded: ['gmap-ui-floating', 'gmap-ctrl-btn', 'gmap-popup-menu'],
        }}
        doubleClick={{ mode: 'zoomIn', step: 0.5 }}
        onPanningStart={(_ref, event) => {
          dragStartPos.current = {
            x: 'clientX' in event ? event.clientX : 0,
            y: 'clientY' in event ? event.clientY : 0,
          };
        }}
        onPanning={(_ref, event) => {
          if (dragStartPos.current && 'clientX' in event) {
            const dx = Math.abs(event.clientX - dragStartPos.current.x);
            const dy = Math.abs(event.clientY - dragStartPos.current.y);
            if (dx > 4 || dy > 4) {
              isDraggingRef.current = true;
            }
          }
        }}
        onPanningStop={() => {
          setTimeout(() => {
            isDraggingRef.current = false;
          }, 80);
        }}
        onTransform={(ref, state) => {
          const s = state?.scale ?? ref?.state?.scale;
          if (typeof s === 'number') {
            applyPinScale(s);
          }
        }}
      >
        {({ zoomIn, zoomOut }) => (
          <div className="gmap-canvas-wrapper">
            <TransformComponent
              wrapperClass="gmap-transform-viewport"
              contentClass="gmap-transform-content"
            >
              <div
                ref={canvasRef}
                className={`gmap-canvas ${showLabels ? 'with-labels' : ''}`}
                style={{
                  width: `${dimensions.width}px`,
                  height: `${dimensions.height}px`,
                  '--split-x': `${threshold}%`,
                  '--split-y': `${100 - threshold}%`,
                  '--pin-scale': '1',
                } as CSSProperties}
              >
                {/* Quadrant Sector Backgrounds (Map Districts) */}
                <div className="gmap-district district-stretch">
                  <div
                    className="district-watermark"
                    style={{ transform: 'scale(var(--pin-scale, 1))', transformOrigin: 'top left' }}
                  >
                    <span className="district-tag">SECTOR II</span>
                    <h3>Stretch Reach</h3>
                    <p>High Ambition · Reach Opportunities</p>
                  </div>
                </div>

                <div className="gmap-district district-sweet">
                  <div
                    className="district-watermark"
                    style={{ transform: 'scale(var(--pin-scale, 1))', transformOrigin: 'top right' }}
                  >
                    <span className="district-tag sweet-tag">
                      <Sparkles size={11} className="inline mr-1" /> PRIME SECTOR
                    </span>
                    <h3>Sweet Spot</h3>
                    <p>Top Profile Alignment & Domain Fit</p>
                  </div>
                </div>

                <div className="gmap-district district-low">
                  <div
                    className="district-watermark"
                    style={{ transform: 'scale(var(--pin-scale, 1))', transformOrigin: 'bottom left' }}
                  >
                    <span className="district-tag">SECTOR III</span>
                    <h3>Exploration</h3>
                    <p>Secondary & Emerging Matches</p>
                  </div>
                </div>

                <div className="gmap-district district-safety">
                  <div
                    className="district-watermark"
                    style={{ transform: 'scale(var(--pin-scale, 1))', transformOrigin: 'bottom right' }}
                  >
                    <span className="district-tag">SECTOR IV</span>
                    <h3>Safety Harbor</h3>
                    <p>High Feasibility · Secure Alignment</p>
                  </div>
                </div>

                {/* Clean Precision Grid & Coordinate Lines */}
                <svg className="gmap-grid-layer" width="100%" height="100%" aria-hidden="true">
                  <defs>
                    <radialGradient id="heatGlow" cx="65%" cy="35%" r="45%">
                      <stop offset="0%" stopColor="#10b981" stopOpacity="0.18" />
                      <stop offset="50%" stopColor="#06b6d4" stopOpacity="0.08" />
                      <stop offset="100%" stopColor="transparent" stopOpacity="0" />
                    </radialGradient>
                  </defs>

                  {mapStyle === 'heatmap' && (
                    <rect width="100%" height="100%" fill="url(#heatGlow)" />
                  )}

                  {/* Subtle Grid Coordinates */}
                  {[25, 50, 75].map((pct) => (
                    <g key={pct}>
                      <line x1={`${pct}%`} x2={`${pct}%`} y1="0%" y2="100%" className="grid-subtle-line" />
                      <line x1="0%" x2="100%" y1={`${pct}%`} y2={`${pct}%`} className="grid-subtle-line" />
                    </g>
                  ))}

                  {/* Threshold Split Boundaries */}
                  <line
                    x1={`${threshold}%`}
                    x2={`${threshold}%`}
                    y1="0%"
                    y2="100%"
                    className="grid-boundary-line vertical-boundary"
                  />
                  <line
                    x1="0%"
                    x2="100%"
                    y1={`${100 - threshold}%`}
                    y2={`${100 - threshold}%`}
                    className="grid-boundary-line horizontal-boundary"
                  />

                  {/* Marker Collision Leader Lines (Rendered ONLY for displaced pins) */}
                  {visibleLeaders.map((m) => (
                    <g key={`leader-${m.job.id}`} className="gmap-leader-group">
                      <line
                        x1={m.trueX}
                        y1={m.trueY}
                        x2={m.px}
                        y2={m.py}
                        className={`gmap-leader-line ${hoveredId === m.job.id ? 'highlighted' : ''}`}
                      />
                      <circle
                        cx={m.trueX}
                        cy={m.trueY}
                        r={hoveredId === m.job.id ? 3 : 2}
                        className="gmap-leader-anchor"
                      />
                    </g>
                  ))}
                </svg>

                {/* Axis Labels Overlay positioned along the quadrant division lines (never covered by toolbars) */}
                <div
                  className="gmap-axis-tag gmap-axis-x"
                  style={{
                    left: `${Math.min(threshold + 4, 82)}%`,
                    bottom: '72px',
                    transform: 'scale(var(--pin-scale, 1))',
                    transformOrigin: 'bottom left',
                  }}
                >
                  <span className="font-semibold text-primary">X:</span> <span>{xLabel}</span> →
                </div>
                <div
                  className="gmap-axis-tag gmap-axis-y"
                  style={{
                    left: `${Math.min(threshold + 4, 82)}%`,
                    top: '20px',
                    transform: 'scale(var(--pin-scale, 1))',
                    transformOrigin: 'top left',
                  }}
                >
                  <span className="font-semibold text-primary">Y:</span> <span>{yLabel}</span> ↑
                </div>

                {/* Job Location Pins - Each pin is memoized for instant 60fps responsiveness */}
                {markers.map((m) => {
                  const quad = mapQuadrant(m.x, m.y, threshold);
                  const isSelected = selectedId === m.job.id;
                  const isHovered = hoveredId === m.job.id;
                  const isSweet = quad === 'sweet';
                  const recent = isNew(m.job);

                  return (
                    <MapPinMarker
                      key={m.job.id}
                      marker={m}
                      isSelected={isSelected}
                      isHovered={isHovered}
                      isSweet={isSweet}
                      quad={quad}
                      recent={recent}
                      onSelect={handleSelectJob}
                      onHover={handleHoverMarker}
                    />
                  );
                })}

                {/* Google Maps Hover Place Popup / Tooltip with automatic edge clamping and flipping */}
                {tooltipJob && (() => {
                  const isNearTop = tooltipJob.py < 130;
                  const clampedX = Math.max(140, Math.min(dimensions.width - 140, tooltipJob.px));
                  const topPos = isNearTop ? tooltipJob.py + 26 : tooltipJob.py - 16;

                  return (
                    <div
                      className={`gmap-hover-card ${isNearTop ? 'card-below' : 'card-above'}`}
                      style={{
                        left: `${clampedX}px`,
                        top: `${topPos}px`,
                        transform: `translate(-50%, ${isNearTop ? '0' : '-100%'}) scale(var(--pin-scale, 1))`,
                        transformOrigin: isNearTop ? 'top center' : 'bottom center',
                      }}
                    >
                      <div className={`hover-card-inner ${isNearTop ? 'below' : ''}`}>
                        <div className="hover-card-header">
                          <CompanyMark job={tooltipJob.job} />
                          <div className="min-w-0 flex-1">
                            <h4 className="hover-title truncate">{tooltipJob.job.company}</h4>
                            <p className="hover-sub truncate">{tooltipJob.job.title}</p>
                          </div>
                          <div className="hover-score-pill">
                            <span>{tooltipJob.job.score}%</span>
                          </div>
                        </div>
                        <div className="hover-card-meta">
                          <span>{tooltipJob.job.location}</span>
                          <span>·</span>
                          <span>{tooltipJob.job.seniority}</span>
                          <span>·</span>
                          <span className="hover-quad-badge">
                            {mapQuadrant(tooltipJob.x, tooltipJob.y, threshold).toUpperCase()}
                          </span>
                        </div>
                        <div className="hover-hint">Click pin to view full opportunity</div>
                      </div>
                    </div>
                  );
                })()}
              </div>
            </TransformComponent>

            {/* Google Maps Floating Controls (Bottom-Right) */}
            <div className="gmap-ctrl-cluster gmap-ui-floating" onClick={(e) => e.stopPropagation()}>
              {/* Layers Switcher Menu */}
              {showLayerMenu && (
                <div className="gmap-popup-menu layers-menu">
                  <div className="menu-header flex items-center justify-between">
                    <span>Map Display Mode</span>
                    <button
                      onClick={() => setShowLayerMenu(false)}
                      className="text-slate-400 hover:text-slate-700 cursor-pointer p-0.5"
                      title="Close"
                    >
                      <X size={13} />
                    </button>
                  </div>
                  <button
                    className={`menu-item ${mapStyle === 'carto' ? 'active' : ''}`}
                    onClick={() => {
                      setMapStyle('carto');
                      setShowLayerMenu(false);
                    }}
                  >
                    <span className="menu-icon">🗺️</span>
                    <div>
                      <strong>Carto Vector</strong>
                      <p>Clean atlas view with clear district divisions</p>
                    </div>
                  </button>
                  <button
                    className={`menu-item ${mapStyle === 'satellite' ? 'active' : ''}`}
                    onClick={() => {
                      setMapStyle('satellite');
                      setShowLayerMenu(false);
                    }}
                  >
                    <span className="menu-icon">🛰️</span>
                    <div>
                      <strong>Deep Radar Satellite</strong>
                      <p>High-contrast dark matrix with glowing beacons</p>
                    </div>
                  </button>
                  <button
                    className={`menu-item ${mapStyle === 'heatmap' ? 'active' : ''}`}
                    onClick={() => {
                      setMapStyle('heatmap');
                      setShowLayerMenu(false);
                    }}
                  >
                    <span className="menu-icon">🔥</span>
                    <div>
                      <strong>Opportunity Heatmap</strong>
                      <p>Density visualization of high-fit clusters</p>
                    </div>
                  </button>
                </div>
              )}

              {/* Axes Configuration Menu */}
              {showAxesMenu && (
                <div className="gmap-popup-menu axes-menu">
                  <div className="menu-header flex items-center justify-between">
                    <span>Configure Fit Matrix</span>
                    <button
                      onClick={() => setShowAxesMenu(false)}
                      className="text-slate-400 hover:text-slate-700 cursor-pointer p-0.5"
                      title="Close"
                    >
                      <X size={13} />
                    </button>
                  </div>
                  <div className="axes-form-group">
                    <label>Horizontal (X-Axis):</label>
                    <select
                      value={xAxis}
                      onChange={(e) => onAxesChange(e.target.value as MapAxis, yAxis)}
                    >
                      {mapAxes.map((a) => (
                        <option key={a.value} value={a.value}>
                          {a.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="axes-form-group">
                    <label>Vertical (Y-Axis):</label>
                    <select
                      value={yAxis}
                      onChange={(e) => onAxesChange(xAxis, e.target.value as MapAxis)}
                    >
                      {mapAxes.map((a) => (
                        <option key={a.value} value={a.value}>
                          {a.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="axes-form-group">
                    <label>Quadrant Split Line: <strong>{threshold}%</strong></label>
                    <input
                      type="range"
                      min={25}
                      max={75}
                      step={5}
                      value={threshold}
                      onChange={(e) => onThresholdChange(Number(e.target.value))}
                    />
                  </div>
                  <button
                    className="menu-reset-btn"
                    onClick={() => {
                      onAxesChange('technical', 'domain');
                      onThresholdChange(50);
                      setShowAxesMenu(false);
                    }}
                  >
                    Reset to Default Fit Matrix
                  </button>
                </div>
              )}

              {/* Layer Switcher Button */}
              <button
                className={`gmap-ctrl-btn ${showLayerMenu ? 'btn-active' : ''}`}
                title="Map layers & theme"
                onClick={() => {
                  setShowLayerMenu(!showLayerMenu);
                  setShowAxesMenu(false);
                }}
              >
                <Layers size={17} />
              </button>

              {/* Axes / Matrix Config Button */}
              <button
                className={`gmap-ctrl-btn ${showAxesMenu ? 'btn-active' : ''}`}
                title="Configure axes & matrix threshold"
                onClick={() => {
                  setShowAxesMenu(!showAxesMenu);
                  setShowLayerMenu(false);
                }}
              >
                <SlidersHorizontal size={17} />
              </button>

              {/* Labels Toggle Button */}
              <button
                className={`gmap-ctrl-btn ${showLabels ? 'btn-active' : ''}`}
                title={showLabels ? 'Hide company labels' : 'Show company labels'}
                onClick={() => setShowLabels(!showLabels)}
              >
                <Tags size={17} />
              </button>

              {/* Divider */}
              <div className="gmap-ctrl-divider" />

              {/* Recenter / Fit Button */}
              <button
                className="gmap-ctrl-btn"
                title="Recenter and fit map"
                onClick={handleRecenter}
              >
                <Crosshair size={17} />
              </button>

              {/* Zoom In Button */}
              <button
                className="gmap-ctrl-btn"
                title="Zoom in (+)"
                onClick={() => zoomIn()}
              >
                <Plus size={18} />
              </button>

              {/* Zoom Out Button */}
              <button
                className="gmap-ctrl-btn"
                title="Zoom out (-)"
                onClick={() => zoomOut()}
              >
                <Minus size={18} />
              </button>

              {/* Fullscreen Toggle */}
              <button
                className="gmap-ctrl-btn"
                title="Toggle fullscreen"
                onClick={toggleFullscreen}
              >
                {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
              </button>
            </div>
          </div>
        )}
      </TransformWrapper>
    </div>
  );
}
