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
import { MAX_MAP_PINS } from '@/lib/perf';
import { Presence } from '@/components/ui/presence';
import { CompanyMark } from './match-matrix';

export type MapStyleMode = 'carto' | 'satellite' | 'heatmap';

export interface GoogleMapViewProps {
  jobs: Job[];
  selectedId: string | null;
  hoveredId: string | null;
  onSelectJob: (id: string) => void;
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
  index: number;
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
  index,
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
      style={
        {
          transform: `translate3d(${px}px, ${py}px, 0)`,
          '--pin-delay': `${Math.min(index * 14, 700)}ms`,
        } as CSSProperties
      }
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      role="button"
      tabIndex={0}
      aria-label={`${job.company} - ${job.title}`}
    >
      <div className="pin-anchor" style={{ transform: 'translate(-50%, -50%) scale(var(--pin-scale, 1))' }}>
        {/* Google Maps Pin Teardrop/Disc Body */}
        <div className="pin-body">
          <CompanyMark job={job} />
          {recent && <span className="pin-new-badge" title="Discovered recently" />}
          {/* Match Score Badge on Pin (anchored to top-right of the circular body) */}
          <span className="pin-score-badge">{job.score}%</span>
        </div>

        {/* Pin Street/Company Label */}
        <div className="pin-label">
          <span className="pin-company-name">{job.company}</span>
          <span className="pin-job-title">{job.title}</span>
        </div>
      </div>
    </div>
  );
});

export const GoogleMapView = memo(function GoogleMapView({
  jobs,
  selectedId,
  hoveredId,
  onSelectJob,
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
  const [currentZoom, setCurrentZoom] = useState(1);

  // Vast Infinite World Dimensions: seamless navigation plane in all directions
  const WORLD_W = 7000;
  const WORLD_H = 5000;
  const worldCenterX = WORLD_W / 2;
  const worldCenterY = WORLD_H / 2;

  // Matrix Opportunity Area centered in the vast world
  const MATRIX_W = Math.max(1400, dimensions.width);
  const MATRIX_H = Math.max(900, dimensions.height);
  const matrixOriginX = worldCenterX - MATRIX_W / 2;
  const matrixOriginY = worldCenterY - MATRIX_H / 2;

  // Quadrant Split Crosshair in World Coordinates
  const splitX = matrixOriginX + (threshold / 100) * MATRIX_W;
  const splitY = matrixOriginY + ((100 - threshold) / 100) * MATRIX_H;

  const [mapStyle, setMapStyle] = useState<MapStyleMode>('carto');
  const [showLabels, setShowLabels] = useState(false);
  const [showAxesMenu, setShowAxesMenu] = useState(false);
  const [showLayerMenu, setShowLayerMenu] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [tooltipJob, setTooltipJob] = useState<{ job: Job; px: number; py: number; x: number; y: number } | null>(null);

  const isDraggingRef = useRef(false);
  const dragStartPos = useRef<{ x: number; y: number } | null>(null);
  const rafId = useRef<number | null>(null);
  const lastScaleRef = useRef(1);
  const transformStateRef = useRef<{ scale: number; positionX: number; positionY: number }>({
    scale: 1,
    positionX: 0,
    positionY: 0,
  });
  const prevSelectedIdRef = useRef<string | null>(null);

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
      const width = Math.max(800, Math.round(rect.width));
      const height = Math.max(600, Math.round(rect.height));
      setDimensions((prev) => (prev.width === width && prev.height === height ? prev : { width, height }));
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

  // Compute positioned markers with collision avoidance in World Coordinates
  const markers = useMemo(() => {
    const placed = positionMarkers(jobs, xAxis, yAxis, MATRIX_W, MATRIX_H, MAX_MAP_PINS);
    return placed.map((m) => ({
      ...m,
      px: matrixOriginX + m.px,
      py: matrixOriginY + m.py,
      trueX: matrixOriginX + m.trueX,
      trueY: matrixOriginY + m.trueY,
    }));
  }, [jobs, xAxis, yAxis, MATRIX_W, MATRIX_H, matrixOriginX, matrixOriginY]);

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

  // Recenter / Fit map to bounds: snaps back to content center of the infinite plane (manual button only)
  const handleRecenter = () => {
    if (transformRef.current) {
      const targetX = Math.round(dimensions.width / 2 - worldCenterX);
      const targetY = Math.round(dimensions.height / 2 - worldCenterY);
      transformRef.current.setTransform(targetX, targetY, 1, 550, 'easeOutQuart');
      transformStateRef.current = { scale: 1, positionX: targetX, positionY: targetY };
      applyPinScale(1);
      setCurrentZoom(1);
    }
  };

  // Natural selection handling:
  // 1. When an icon is clicked, keep the graph AT ITS EXACT CURRENT POSITION AND CURRENT ZOOM.
  //    Only gently slide horizontally if the clicked icon would be hidden behind the place card.
  // 2. When closing the popup, NEVER reset the graph to 100%. The graph stays exactly where it was.
  useEffect(() => {
    if (selectedId === prevSelectedIdRef.current) return;
    prevSelectedIdRef.current = selectedId;

    // Closing popup: NEVER reset or move the map! Preserve zoom and pan completely.
    if (!selectedId || !transformRef.current) return;

    const target = markers.find((m) => m.job.id === selectedId);
    if (!target) return;

    const currentTransform = transformRef.current.state ?? transformStateRef.current;
    const currentScale = currentTransform.scale > 0 ? currentTransform.scale : 1;
    const currentPosX = currentTransform.positionX;
    const currentPosY = currentTransform.positionY;

    // Calculate marker's current position on the user's screen
    const screenX = target.px * currentScale + currentPosX;
    const screenY = target.py * currentScale + currentPosY;

    const isMobile = dimensions.width < 768;
    const cardWidth = isMobile ? 0 : 470; // 440px place card + margin

    // Check if marker is already visible in the clear viewport area
    const isVisible =
      screenX >= cardWidth + 30 &&
      screenX <= dimensions.width - 40 &&
      screenY >= 60 &&
      screenY <= dimensions.height - 60;

    // If marker is already visible under the user's cursor, DO NOT move the map!
    if (isVisible) return;

    // If marker falls under the place card on the left (screenX < cardWidth + 30)
    // but is in vertical view: gently slide X right just enough so the pin clears the card.
    // Notice: Zoom scale is 100% PRESERVED, Y position is 100% PRESERVED!
    if (screenX < cardWidth + 30 && screenY >= 40 && screenY <= dimensions.height - 40) {
      const neededShift = Math.round(cardWidth + 60 - screenX);
      const targetX = currentPosX + neededShift;
      transformRef.current.setTransform(targetX, currentPosY, currentScale, 450, 'easeOutQuart');
      transformStateRef.current = { scale: currentScale, positionX: targetX, positionY: currentPosY };
      return;
    }

    // If marker was selected from off-screen (e.g. from bottom drawer "View on Map"):
    // smoothly center it in the unobstructed area, preserving the user's current zoom scale!
    const visibleCenterX = isMobile ? dimensions.width / 2 : (dimensions.width + cardWidth) / 2;
    const visibleCenterY = dimensions.height / 2;
    const targetX = Math.round(visibleCenterX - target.px * currentScale);
    const targetY = Math.round(visibleCenterY - target.py * currentScale);

    transformRef.current.setTransform(targetX, targetY, currentScale, 600, 'easeOutQuart');
    transformStateRef.current = { scale: currentScale, positionX: targetX, positionY: targetY };
  }, [selectedId, dimensions.width, dimensions.height, markers]);

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
      setTooltipJob(marker);
    },
    []
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
        minScale={0.35}
        maxScale={4.5}
        initialScale={1}
        limitToBounds={false}
        centerOnInit={false}
        initialPositionX={Math.round(dimensions.width / 2 - worldCenterX)}
        initialPositionY={Math.round(dimensions.height / 2 - worldCenterY)}
        smooth
        wheel={{ step: 0.06 }}
        zoomAnimation={{ animationTime: 320, animationType: 'easeOutQuart' }}
        panning={{
          velocityDisabled: true,
          excluded: ['gmap-ui-floating', 'gmap-ctrl-btn', 'gmap-popup-menu'],
        }}
        doubleClick={{ mode: 'zoomIn', step: 0.5, animationTime: 450, animationType: 'easeOutQuart' }}
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
        onPanningStop={(ref) => {
          setTimeout(() => {
            isDraggingRef.current = false;
          }, 80);
          const state = ref?.state;
          if (state && typeof state.scale === 'number') {
            transformStateRef.current = {
              scale: state.scale,
              positionX: state.positionX ?? 0,
              positionY: state.positionY ?? 0,
            };
          }
        }}
        onZoomStop={(ref) => {
          const state = ref?.state;
          if (state && typeof state.scale === 'number') {
            setCurrentZoom(state.scale);
            transformStateRef.current = {
              scale: state.scale,
              positionX: state.positionX ?? 0,
              positionY: state.positionY ?? 0,
            };
          }
        }}
        onTransform={(ref, state) => {
          const s = state?.scale ?? ref?.state?.scale;
          const px = state?.positionX ?? ref?.state?.positionX;
          const py = state?.positionY ?? ref?.state?.positionY;
          if (typeof s === 'number') {
            transformStateRef.current.scale = s;
            applyPinScale(s);
          }
          if (typeof px === 'number') transformStateRef.current.positionX = px;
          if (typeof py === 'number') transformStateRef.current.positionY = py;
        }}
      >
        {({ zoomIn, zoomOut }) => (
          <div className="gmap-canvas-wrapper">
            {/* 4 Engraved Corner Quadrant Watermarks (Ground Layer: rendered under pins and canvas elements) */}
            <div className="gmap-corner-watermark corner-top-left" aria-hidden="true">
              <span className="corner-tag">SECTOR II</span>
              <h3 className="corner-title">Stretch Reach</h3>
              <p className="corner-sub">High Ambition · Reach</p>
            </div>

            <div className="gmap-corner-watermark corner-top-right" aria-hidden="true">
              <span className="corner-tag sweet-tag">
                <Sparkles size={11} className="inline mr-1" /> PRIME SECTOR
              </span>
              <h3 className="corner-title text-emerald-700/80 dark:text-emerald-400/80">Sweet Spot</h3>
              <p className="corner-sub">Top Profile Alignment</p>
            </div>

            <div className="gmap-corner-watermark corner-bottom-left" aria-hidden="true">
              <span className="corner-tag">SECTOR III</span>
              <h3 className="corner-title">Exploration</h3>
              <p className="corner-sub">Emerging Matches</p>
            </div>

            <div className="gmap-corner-watermark corner-bottom-right" aria-hidden="true">
              <span className="corner-tag">SECTOR IV</span>
              <h3 className="corner-title">Safety Harbor</h3>
              <p className="corner-sub">High Feasibility</p>
            </div>

            <TransformComponent
              wrapperClass="gmap-transform-viewport"
              contentClass="gmap-transform-content"
            >
              <div
                ref={canvasRef}
                className={`gmap-canvas ${showLabels ? 'with-labels' : ''}`}
                style={{
                  width: `${WORLD_W}px`,
                  height: `${WORLD_H}px`,
                  '--pin-scale': '1',
                } as CSSProperties}
              >
                {/* 4 Infinite Atmospheric Quadrants radiating outward from the split crosshair */}
                <div
                  className="gmap-district district-stretch"
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    width: `${splitX}px`,
                    height: `${splitY}px`,
                    background:
                      mapStyle === 'satellite'
                        ? 'radial-gradient(ellipse at 100% 100%, rgba(245, 158, 11, 0.1) 0%, rgba(245, 158, 11, 0.03) 40%, transparent 75%)'
                        : mapStyle === 'heatmap'
                        ? 'radial-gradient(ellipse at 100% 100%, rgba(245, 158, 11, 0.15) 0%, transparent 65%)'
                        : 'radial-gradient(ellipse at 100% 100%, rgba(245, 158, 11, 0.12) 0%, rgba(254, 243, 199, 0.04) 40%, transparent 75%)',
                  }}
                />
                <div
                  className="gmap-district district-sweet"
                  style={{
                    position: 'absolute',
                    left: `${splitX}px`,
                    top: 0,
                    width: `${WORLD_W - splitX}px`,
                    height: `${splitY}px`,
                    background:
                      mapStyle === 'satellite'
                        ? 'radial-gradient(ellipse at 0% 100%, rgba(16, 185, 129, 0.16) 0%, rgba(6, 182, 212, 0.05) 45%, transparent 75%)'
                        : mapStyle === 'heatmap'
                        ? 'radial-gradient(ellipse at 0% 100%, rgba(16, 185, 129, 0.25) 0%, rgba(6, 182, 212, 0.1) 50%, transparent 80%)'
                        : 'radial-gradient(ellipse at 0% 100%, rgba(16, 185, 129, 0.15) 0%, rgba(209, 250, 229, 0.05) 45%, transparent 75%)',
                  }}
                />
                <div
                  className="gmap-district district-low"
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: `${splitY}px`,
                    width: `${splitX}px`,
                    height: `${WORLD_H - splitY}px`,
                    background:
                      mapStyle === 'satellite'
                        ? 'radial-gradient(ellipse at 100% 0%, rgba(71, 85, 105, 0.12) 0%, transparent 70%)'
                        : 'radial-gradient(ellipse at 100% 0%, rgba(148, 163, 184, 0.1) 0%, transparent 70%)',
                  }}
                />
                <div
                  className="gmap-district district-safety"
                  style={{
                    position: 'absolute',
                    left: `${splitX}px`,
                    top: `${splitY}px`,
                    width: `${WORLD_W - splitX}px`,
                    height: `${WORLD_H - splitY}px`,
                    background:
                      mapStyle === 'satellite'
                        ? 'radial-gradient(ellipse at 0% 0%, rgba(59, 130, 246, 0.12) 0%, transparent 70%)'
                        : 'radial-gradient(ellipse at 0% 0%, rgba(59, 130, 246, 0.11) 0%, rgba(219, 234, 254, 0.04) 45%, transparent 75%)',
                  }}
                />

                {/* Clean Precision Grid & Coordinate Lines across the whole vast plane */}
                <svg className="gmap-grid-layer" width={WORLD_W} height={WORLD_H} aria-hidden="true">
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

                  {/* Matrix Coordinate Subdivisions */}
                  {[0.25, 0.5, 0.75].map((pct) => (
                    <g key={pct}>
                      <line
                        x1={matrixOriginX + pct * MATRIX_W}
                        x2={matrixOriginX + pct * MATRIX_W}
                        y1={matrixOriginY}
                        y2={matrixOriginY + MATRIX_H}
                        className="grid-subtle-line"
                      />
                      <line
                        x1={matrixOriginX}
                        x2={matrixOriginX + MATRIX_W}
                        y1={matrixOriginY + pct * MATRIX_H}
                        y2={matrixOriginY + pct * MATRIX_H}
                        className="grid-subtle-line"
                      />
                    </g>
                  ))}

                  {/* Infinite Threshold Split Crosshair Axes extending end-to-end */}
                  <line
                    x1="0"
                    y1={splitY}
                    x2={WORLD_W}
                    y2={splitY}
                    className="grid-infinite-axis"
                  />
                  <line
                    x1={splitX}
                    y1="0"
                    x2={splitX}
                    y2={WORLD_H}
                    className="grid-infinite-axis"
                  />

                  {/* Precision Reticle at Threshold Crosshair */}
                  <g className="gmap-reticle" transform={`translate(${splitX}, ${splitY})`}>
                    <circle r="12" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
                    <circle r="2.5" fill="currentColor" opacity="0.8" />
                    <line x1="-18" y1="0" x2="-5" y2="0" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
                    <line x1="5" y1="0" x2="18" y2="0" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
                    <line x1="0" y1="-18" x2="0" y2="-5" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
                    <line x1="0" y1="5" x2="0" y2="18" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
                  </g>
                </svg>

                {/* Axis Labels Overlay positioned along the infinite coordinate axes */}
                <div
                  className="gmap-axis-tag gmap-axis-x"
                  style={{
                    left: `${matrixOriginX + MATRIX_W - 130}px`,
                    top: `${splitY + 12}px`,
                    transform: 'scale(var(--pin-scale, 1))',
                    transformOrigin: 'top left',
                  }}
                >
                  <span className="font-semibold text-primary">X:</span> <span>{xLabel}</span> →
                </div>
                <div
                  className="gmap-axis-tag gmap-axis-y"
                  style={{
                    left: `${splitX + 14}px`,
                    top: `${matrixOriginY + 18}px`,
                    transform: 'scale(var(--pin-scale, 1))',
                    transformOrigin: 'top left',
                  }}
                >
                  <span className="font-semibold text-primary">Y:</span> <span>{yLabel}</span> ↑
                </div>

                {/* Job Location Pins - Each pin is memoized for instant 60fps responsiveness */}
                {markers.map((m, i) => {
                  const quad = mapQuadrant(m.x, m.y, threshold);
                  const isSelected = selectedId === m.job.id;
                  const isHovered = tooltipJob?.job.id === m.job.id;
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
                      index={i}
                      onSelect={handleSelectJob}
                      onHover={handleHoverMarker}
                    />
                  );
                })}

                {/* Google Maps Hover Place Popup / Tooltip */}
                {tooltipJob && (() => {
                  const isNearTop = tooltipJob.py < matrixOriginY + 140;
                  const topPos = isNearTop ? tooltipJob.py + 26 : tooltipJob.py - 16;

                  return (
                    <div
                      className={`gmap-hover-card ${isNearTop ? 'card-below' : 'card-above'}`}
                      style={{
                        left: `${tooltipJob.px}px`,
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

            {/* Google Maps Dynamic Coordinate Scale Indicator */}
            <div className="gmap-scale-cluster gmap-ui-floating">
              <div className="gmap-scale-indicator">
                <div className="scale-bar" />
                <span>{`±${Math.max(2, Math.round(12 / (currentZoom || 1)))}% Resolution`}</span>
              </div>
            </div>

            {/* Google Maps Floating Controls (Bottom-Right) */}
            <div className="gmap-ctrl-cluster gmap-ui-floating" onClick={(e) => e.stopPropagation()}>
              {/* Layers Switcher Menu */}
              <Presence show={showLayerMenu} exitMs={170}>
                {(st) => (
                <div
                  className="gmap-popup-menu layers-menu motion-pop"
                  data-state={st}
                  style={{ '--origin': 'bottom right' } as CSSProperties}
                >
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
              </Presence>

              {/* Axes Configuration Menu */}
              <Presence show={showAxesMenu} exitMs={170}>
                {(st) => (
                <div
                  className="gmap-popup-menu axes-menu motion-pop"
                  data-state={st}
                  style={{ '--origin': 'bottom right' } as CSSProperties}
                >
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
              </Presence>

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
});
