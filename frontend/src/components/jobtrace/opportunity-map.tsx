import { useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent } from 'react';
import { Minus, Plus, Scan, Tags } from 'lucide-react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import { Button } from '@/components/ui/button';
import { mapAxes, mapQuadrant, positionMarkers, type Job, type MapAxis } from '@/lib/jobs';
import { CompanyMark } from './match-matrix';
import { MapPopup } from './map-popup';

export function OpportunityMap({
  jobs,
  selectedId,
  popupFor,
  onMarkerSelect,
  onClosePopup,
  onDetails,
  comparing,
  onCompare,
  isNew,
  xAxis,
  yAxis,
  threshold,
  reset,
}: {
  jobs: Job[];
  selectedId: string | undefined;
  popupFor: string | null;
  onMarkerSelect: (id: string) => void;
  onClosePopup: () => void;
  onDetails: (id: string) => void;
  comparing: string[];
  onCompare: (id: string) => void;
  isNew: (job: Job) => boolean;
  xAxis: MapAxis;
  yAxis: MapAxis;
  threshold: number;
  reset: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 900, height: 350 });
  const [scale, setScale] = useState(1);
  const [labels, setLabels] = useState(false);
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) {
        setSize({
          width: Math.max(280, entry.contentRect.width - 27),
          height: Math.max(260, entry.contentRect.height - 30),
        });
      }
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const markers = useMemo(() => {
    return positionMarkers(jobs, xAxis, yAxis, size.width, size.height);
  }, [jobs, xAxis, yAxis, size.width, size.height]);
  const xLabel = mapAxes.find((a) => a.value === xAxis)?.label;
  const yLabel = mapAxes.find((a) => a.value === yAxis)?.label;
  const popupMarker = markers.find((m) => m.job.id === popupFor);

  const onBackgroundClick = (event: MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target.closest('.map-marker') || target.closest('.map-popup')) return;
    onClosePopup();
  };

  return (
    <TransformWrapper
      minScale={1}
      maxScale={5}
      smooth
      wheel={{ step: 0.0015 }}
      panning={{ excluded: ['map-marker', 'map-popup'] }}
      doubleClick={{ excluded: ['map-marker', 'map-popup'] }}
      keyboard={{ disabled: false }}
      onTransform={(_, state) => setScale(state.scale)}
    >
      {({ zoomIn, zoomOut, resetTransform }) => (
        <div className="opportunity-map-shell">
          <div className="map-zoom-controls" aria-label="Chart navigation">
            <Button
              size="icon"
              variant="ghost"
              title="Zoom out"
              aria-label="Zoom out"
              disabled={scale <= 1.001}
              onClick={() => zoomOut()}
            >
              <Minus size={14} />
            </Button>
            <output aria-label="Chart zoom">{Math.round(scale * 100)}%</output>
            <Button
              size="icon"
              variant="ghost"
              title="Zoom in"
              aria-label="Zoom in"
              disabled={scale >= 4.999}
              onClick={() => zoomIn()}
            >
              <Plus size={14} />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              title="Fit chart"
              aria-label="Fit chart"
              onClick={() => resetTransform()}
            >
              <Scan size={14} />
            </Button>
            <Button
              size="icon"
              variant={labels ? 'secondary' : 'ghost'}
              title="Company labels"
              aria-label="Company labels"
              aria-pressed={labels}
              onClick={() => setLabels(!labels)}
            >
              <Tags size={14} />
            </Button>
          </div>

          <div className="map-y-title">
            {yLabel} <span>(0–100%)</span>
          </div>

          <div ref={ref} className="map-chart-scroll">
            <TransformComponent wrapperClass="map-transform-viewport" contentClass="map-transform-content">
              <div
                className={`map-chart-inner ${labels ? 'show-labels' : ''}`}
                style={{
                  '--canvas-width': `${size.width + 27}px`,
                  '--canvas-height': `${size.height}px`,
                } as CSSProperties}
              >
                <div className="map-y-ticks">
                  {[100, 75, 50, 25, 0].map((v) => (
                    <span key={v}>{v}</span>
                  ))}
                </div>

                <div
                  className="opportunity-plot"
                  role="group"
                  aria-label="Strategic opportunity matrix"
                  style={{
                    '--split-x': `${threshold}%`,
                    '--split-y': `${100 - threshold}%`,
                  } as CSSProperties}
                  onClick={onBackgroundClick}
                >
                  <div className="quadrant quadrant-stretch">
                    <span>Stretch reach</span>
                  </div>
                  <div className="quadrant quadrant-sweet">
                    <span>
                      Sweet spot <span className="quadrant-note">· Prime fit</span>
                    </span>
                  </div>
                  <div className="quadrant quadrant-low">
                    <span>
                      Low priority <span className="quadrant-note">· Secondary</span>
                    </span>
                  </div>
                  <div className="quadrant quadrant-safety">
                    <span>Safety roles</span>
                  </div>

                  <svg className="map-grid" width="100%" height="100%" aria-hidden="true">
                    {[25, 50, 75].map((v) => (
                      <g key={v}>
                        <line x1={`${v}%`} x2={`${v}%`} y1="0%" y2="100%" />
                        <line x1="0%" x2="100%" y1={`${v}%`} y2={`${v}%`} />
                      </g>
                    ))}
                    <line
                      className="split-line"
                      x1={`${threshold}%`}
                      x2={`${threshold}%`}
                      y1="0"
                      y2="100%"
                    />
                    <line
                      className="split-line"
                      y1={`${100 - threshold}%`}
                      y2={`${100 - threshold}%`}
                      x1="0"
                      x2="100%"
                    />
                    {markers.map((m) => (
                      <g key={m.job.id} className="leader">
                        <line x1={m.trueX} y1={m.trueY} x2={m.px} y2={m.py} />
                        <circle cx={m.trueX} cy={m.trueY} r="2" />
                      </g>
                    ))}
                  </svg>

                  {markers.map((m) => (
                    <Button
                      key={m.job.id}
                      variant="ghost"
                      className={`map-marker marker-${mapQuadrant(m.x, m.y, threshold)} ${
                        selectedId === m.job.id ? 'active' : ''
                      }`}
                      style={{
                        '--point-x': `${(m.px / size.width) * 100}%`,
                        '--point-y': `${(m.py / size.height) * 100}%`,
                      } as CSSProperties}
                      onClick={() => onMarkerSelect(m.job.id)}
                      onMouseEnter={() => setHover(m.job.id)}
                      onMouseLeave={() => setHover(null)}
                      onFocus={() => setHover(m.job.id)}
                      onBlur={() => setHover(null)}
                      aria-label={`View ${m.job.company} ${m.job.title}, ${xLabel} ${m.x}%, ${yLabel} ${m.y}%`}
                      aria-haspopup="dialog"
                      aria-expanded={popupFor === m.job.id}
                    >
                      <CompanyMark job={m.job} />
                      <span className="marker-company">{m.job.company}</span>
                      {isNew(m.job) && <i className="new-dot" title="New since your last visit" />}
                    </Button>
                  ))}

                  {popupMarker && (
                    <MapPopup
                      job={popupMarker.job}
                      x={popupMarker.px}
                      y={popupMarker.py}
                      width={size.width}
                      comparing={comparing.includes(popupMarker.job.id)}
                      onCompare={() => onCompare(popupMarker.job.id)}
                      onMore={() => {
                        onDetails(popupMarker.job.id);
                        onClosePopup();
                      }}
                    />
                  )}

                  {hover && hover !== popupFor && (() => {
                    const m = markers.find((p) => p.job.id === hover);
                    if (!m) return null;
                    return (
                      <div
                        className="map-tooltip"
                        style={{
                          '--tip-x': `${Math.min(76, Math.max(24, (m.px / size.width) * 100))}%`,
                          '--tip-y': `${Math.min(62, (m.py / size.height) * 100)}%`,
                        } as CSSProperties}
                      >
                        <strong>
                          {m.job.company} · {m.job.title}
                        </strong>
                        <div>
                          {xLabel}: {m.x}%
                        </div>
                        <div>
                          {yLabel}: {m.y}%
                        </div>
                        <div className="mt-1 text-muted-foreground">
                          {m.job.source} · {m.job.location}
                        </div>
                      </div>
                    );
                  })()}

                  {jobs.length === 0 && (
                    <div className="map-empty">
                      <h3>No opportunities found</h3>
                      <Button variant="outline" onClick={reset}>
                        Reset filters
                      </Button>
                    </div>
                  )}
                </div>

                <div className="map-x-ticks">
                  {[0, 25, 50, 75, 100].map((v) => (
                    <span key={v}>{v}</span>
                  ))}
                </div>
              </div>
            </TransformComponent>
          </div>

          <div className="map-x-title">
            {xLabel} <span>(0–100%)</span>
          </div>
        </div>
      )}
    </TransformWrapper>
  );
}
