// Assets live in frontend/public: logo.svg (mark + wordmark) and logo-mark.svg (icon only, also the favicon).
const FULL_RATIO = 768 / 838;

export function Logo({
  size = 28,
  variant = 'mark',
  className = '',
}: {
  size?: number;
  variant?: 'mark' | 'full';
  className?: string;
}) {
  const full = variant === 'full';
  return (
    <img
      src={full ? '/logo.svg' : '/logo-mark.svg'}
      alt="JobTrace"
      width={size}
      height={full ? Math.round(size * FULL_RATIO) : size}
      className={className}
      draggable={false}
    />
  );
}
