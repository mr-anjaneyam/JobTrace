// Low-end detection; override with localStorage "jobtrace.perf" = "lite" | "full".
export function isLowEndDevice(): boolean {
  try {
    const override = localStorage.getItem('jobtrace.perf');
    if (override === 'lite') return true;
    if (override === 'full') return false;
  } catch {
    // storage unavailable
  }
  const nav = navigator as Navigator & { deviceMemory?: number };
  const lowCores = (nav.hardwareConcurrency ?? 8) <= 4;
  const lowMemory = (nav.deviceMemory ?? 8) <= 4;
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  return lowCores || lowMemory || reducedMotion;
}

export const LITE_MODE = isLowEndDevice();

export const MAX_MAP_PINS = LITE_MODE ? 80 : 150;

if (LITE_MODE) document.documentElement.classList.add('perf-lite');
