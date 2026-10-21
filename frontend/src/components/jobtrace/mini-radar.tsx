import { dimensions, type Job } from '@/lib/jobs';

// Precomputed angles for 6 radar axes (starting at top: -90deg, stepping by 60deg)
const ANGLES = [
  -Math.PI / 2,
  -Math.PI / 6,
  Math.PI / 6,
  Math.PI / 2,
  (5 * Math.PI) / 6,
  (-5 * Math.PI) / 6,
];

const CX = 50;
const CY = 50;
const MAX_R = 38;

// Precompute web grid polygons for 25%, 50%, 75%, 100%
const GRID_LEVELS = [0.25, 0.5, 0.75, 1.0].map((level) => {
  const r = MAX_R * level;
  return ANGLES.map((a) => `${(CX + r * Math.cos(a)).toFixed(1)},${(CY + r * Math.sin(a)).toFixed(1)}`).join(' ');
});

const AXIS_LINES = ANGLES.map((a) => ({
  x2: (CX + MAX_R * Math.cos(a)).toFixed(1),
  y2: (CY + MAX_R * Math.sin(a)).toFixed(1),
}));

export function MiniRadar({ job, labels = false }: { job: Job; labels?: boolean }) {
  const breakdown = job.breakdown || [50, 50, 50, 50, 50, 50];

  // Compute polygon points for this job
  const points = ANGLES.map((a, i) => {
    const val = Math.min(100, Math.max(0, breakdown[i] ?? 50));
    const r = (val / 100) * MAX_R;
    const x = (CX + r * Math.cos(a)).toFixed(1);
    const y = (CY + r * Math.sin(a)).toFixed(1);
    return `${x},${y}`;
  }).join(' ');

  return (
    <div
      className={`mini-radar ${labels ? 'with-labels' : ''}`}
      role="img"
      aria-label={`${job.company} match radar: ${dimensions.map((d, i) => `${d} ${breakdown[i] ?? 0}`).join(', ')}`}
      style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
    >
      <svg
        viewBox="0 0 100 100"
        width="100%"
        height="100%"
        style={{ overflow: 'visible', maxWidth: '100%', maxHeight: '100%' }}
      >
        {/* Background Hexagonal Web Grid */}
        {GRID_LEVELS.map((pts, idx) => (
          <polygon
            key={idx}
            points={pts}
            fill={idx === 3 ? 'var(--muted)' : 'none'}
            fillOpacity={idx === 3 ? 0.35 : 0}
            stroke="var(--border)"
            strokeWidth={idx === 3 ? 1 : 0.75}
          />
        ))}

        {/* Radial Axis Lines */}
        {AXIS_LINES.map((axis, idx) => (
          <line
            key={idx}
            x1={CX}
            y1={CY}
            x2={axis.x2}
            y2={axis.y2}
            stroke="var(--border)"
            strokeWidth={0.75}
          />
        ))}

        {/* Job Match Radar Polygon */}
        <polygon
          points={points}
          fill="var(--primary)"
          fillOpacity={0.2}
          stroke="var(--primary)"
          strokeWidth={1.5}
          strokeLinejoin="round"
        />

        {/* Small vertex dots */}
        {ANGLES.map((a, i) => {
          const val = Math.min(100, Math.max(0, breakdown[i] ?? 50));
          const r = (val / 100) * MAX_R;
          const x = CX + r * Math.cos(a);
          const y = CY + r * Math.sin(a);
          return (
            <circle
              key={i}
              cx={x}
              cy={y}
              r={1.75}
              fill="var(--primary)"
            />
          );
        })}
      </svg>
    </div>
  );
}
