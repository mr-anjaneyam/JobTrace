import type { ApiJob } from './api';

export const dimensions = ['Skills', 'Seniority', 'Location', 'Domain', 'Recency', 'Reach'] as const;

export type Job = {
  id: string;
  company: string;
  title: string;
  location: string;
  seniority: string;
  source: string;
  daysAgo: number;
  watched: boolean;
  score: number;
  breakdown: number[];
  reason: string;
  description: string;
  tags: string[];
  mark: string;
  brand: 'ink' | 'sage' | 'clay' | 'gold' | 'lilac';
  url: string;
  domain?: string;
  logoUrl?: string;
  matchedSkills?: string[];
  missingSkills?: string[];
  seniorityFit?: string;
  advice?: string;
  salaryText?: string;
  deadlineText?: string;
  deadlineAt?: number;
};

const BRAND_PALETTE: Array<Job['brand']> = ['ink', 'sage', 'clay', 'gold', 'lilac'];

const KNOWN_DOMAINS: Record<string, string> = {
  anthropic: 'anthropic.com',
  stripe: 'stripe.com',
  notion: 'notion.so',
  figma: 'figma.com',
  databricks: 'databricks.com',
  ramp: 'ramp.com',
  adobe: 'adobe.com',
  nvidia: 'nvidia.com',
  salesforce: 'salesforce.com',
  fidelity: 'fidelity.com',
  oracle: 'oracle.com',
  dell: 'dell.com',
  atlassian: 'atlassian.com',
  openai: 'openai.com',
  gitlab: 'gitlab.com',
  github: 'github.com',
  voodoo: 'voodoo.io',
  'lemon.io': 'lemon.io',
  'a.team': 'a.team',
  'coalition technologies': 'coalitiontechnologies.com',
  linear: 'linear.app',
  vercel: 'vercel.com',
  spotify: 'spotify.com',
  airbnb: 'airbnb.com',
  loom: 'loom.com',
  raycast: 'raycast.com',
  wise: 'wise.com',
  google: 'google.com',
  amazon: 'amazon.com',
  microsoft: 'microsoft.com',
  apple: 'apple.com',
  meta: 'meta.com',
  uber: 'uber.com',
  netflix: 'netflix.com',
  datadog: 'datadoghq.com',
  snowflake: 'snowflake.com',
  cloudflare: 'cloudflare.com',
  telus: 'telusinternational.com',
  'native design': 'native.com',
  'mitre media': 'mitremedia.com',
  distran: 'distran.swiss',
};

function getCompanyDomain(company: string, rawDomain?: string): string {
  if (
    rawDomain &&
    rawDomain.trim() &&
    !rawDomain.includes('myworkdayjobs.com') &&
    !rawDomain.includes('greenhouse.io') &&
    !rawDomain.includes('ashbyhq.com') &&
    !rawDomain.includes('lever.co')
  ) {
    return rawDomain.trim();
  }
  const norm = (company || '').toLowerCase().trim();
  for (const [key, d] of Object.entries(KNOWN_DOMAINS)) {
    if (norm.includes(key)) return d;
  }
  const clean = norm.replace(/[^a-z0-9]/g, '');
  return clean ? `${clean}.com` : '';
}

function getCompanyLogo(company: string, domain?: string): string {
  const d = getCompanyDomain(company, domain);
  if (!d) return '';
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(d)}&sz=128`;
}

const COMPANY_MARKS: Record<string, string> = {
  atlassian: 'A',
  salesforce: '☁',
  linear: '◒',
  notion: 'N',
  figma: 'F',
  vercel: '▲',
  stripe: 'S',
  spotify: '≋',
  loom: '✳',
  airbnb: 'A',
  raycast: '↗',
  wise: 'W',
  google: 'G',
  amazon: 'a',
  microsoft: '⊞',
  apple: '',
  meta: '∞',
  uber: 'U',
  netflix: 'N',
  datadog: 'D',
  snowflake: '❄',
  cloudflare: '☁',
  github: '◈',
  gitlab: '🦊',
};

function getCompanyMark(company: string): string {
  const norm = company.toLowerCase().trim();
  for (const [key, mark] of Object.entries(COMPANY_MARKS)) {
    if (norm.includes(key)) return mark;
  }
  return company.charAt(0).toUpperCase() || '●';
}

function getCompanyBrand(company: string): Job['brand'] {
  let hash = 0;
  for (let i = 0; i < company.length; i++) {
    hash = (hash << 5) - hash + company.charCodeAt(i);
    hash |= 0;
  }
  return BRAND_PALETTE[Math.abs(hash) % BRAND_PALETTE.length];
}

function inferSeniority(title: string, reason?: string): 'Junior' | 'Mid' | 'Senior' {
  const text = `${title} ${reason || ''}`.toLowerCase();
  if (/\b(senior|sr\.?|lead|principal|staff|smts|director|head|vp)\b/i.test(text)) {
    return 'Senior';
  }
  if (/\b(junior|jr\.?|associate|intern|entry|graduate|grad)\b/i.test(text)) {
    return 'Junior';
  }
  return 'Mid';
}

const COMMON_TAGS = [
  'React', 'TypeScript', 'JavaScript', 'Python', 'Go', 'Rust', 'Java', 'C++',
  'Frontend', 'Backend', 'Full Stack', 'Cloud', 'AWS', 'Distributed Systems',
  'DevOps', 'Data', 'ML', 'AI', 'Security', 'Infrastructure', 'Product', 'API'
];

function extractTags(title: string, domain?: string, reason?: string): string[] {
  const text = `${title} ${domain || ''} ${reason || ''}`.toLowerCase();
  const matched: string[] = [];
  for (const tag of COMMON_TAGS) {
    if (text.includes(tag.toLowerCase())) {
      matched.push(tag);
      if (matched.length >= 3) break;
    }
  }
  if (matched.length === 0) {
    matched.push('Engineering', 'Software');
  }
  return matched;
}

export function transformApiJob(apiJob: ApiJob): Job {
  // Normalize score 0..10 -> 0..100
  let normScore = 0;
  if (apiJob.score !== null && apiJob.score !== undefined) {
    normScore = apiJob.score <= 10 ? Math.round(apiJob.score * 10) : Math.min(100, Math.round(apiJob.score));
  }

  // Parse breakdown
  let breakdownVals = [normScore, normScore, 75, normScore, 80, 70];
  let bdObj: Record<string, any> | null = null;
  if (apiJob.breakdown) {
    if (typeof apiJob.breakdown === 'string') {
      try {
        bdObj = JSON.parse(apiJob.breakdown);
      } catch {
        bdObj = null;
      }
    } else if (typeof apiJob.breakdown === 'object') {
      bdObj = apiJob.breakdown as Record<string, any>;
    }

    if (bdObj) {
      breakdownVals = [
        Math.min(100, Math.max(0, Math.round(bdObj.skills ?? normScore))),
        Math.min(100, Math.max(0, Math.round(bdObj.seniority ?? normScore))),
        Math.min(100, Math.max(0, Math.round(bdObj.location ?? 75))),
        Math.min(100, Math.max(0, Math.round(bdObj.domain ?? normScore))),
        Math.min(100, Math.max(0, Math.round(bdObj.recency ?? 80))),
        Math.min(100, Math.max(0, Math.round(bdObj.reach ?? 70))),
      ];
    }
  }

  const matchedSkills: string[] = Array.isArray(bdObj?.matched_skills) ? bdObj!.matched_skills : [];
  const missingSkills: string[] = Array.isArray(bdObj?.missing_skills) ? bdObj!.missing_skills : [];
  const seniorityFit: string = bdObj?.seniority_fit || '';
  const advice: string = bdObj?.advice || '';
  const salaryText: string = apiJob.salary_text || bdObj?.salary_text || '';
  const deadlineText: string = apiJob.deadline_text || bdObj?.deadline_text || '';
  const deadlineAt: number | undefined = apiJob.deadline_at ?? bdObj?.deadline_at;

  // Calculate days ago
  const nowSec = Date.now() / 1000;
  const timeRef = apiJob.posted_at || apiJob.first_seen;
  const daysAgo = timeRef ? Math.max(0, Math.floor((nowSec - timeRef) / 86400)) : 1;

  const seniority = inferSeniority(apiJob.title, apiJob.reason);
  const mark = getCompanyMark(apiJob.company);
  const brand = getCompanyBrand(apiJob.company);
  const tags = extractTags(apiJob.title, apiJob.domain, apiJob.reason);
  const domain = getCompanyDomain(apiJob.company, apiJob.domain);
  const logoUrl = getCompanyLogo(apiJob.company, domain);

  const description =
    apiJob.description?.trim() ||
    `Opportunity at ${apiJob.company} for ${apiJob.title} in ${apiJob.location || 'Remote'}. Evaluated against your active profile with assessment reason: ${apiJob.reason || 'Standard criteria matching'}.`;

  return {
    id: String(apiJob.id),
    company: apiJob.company,
    title: apiJob.title,
    location: apiJob.location || 'Remote',
    seniority,
    source: apiJob.source || 'Direct',
    daysAgo,
    watched: normScore >= 70,
    score: normScore,
    breakdown: breakdownVals,
    reason: apiJob.reason || 'Role matched candidate profile parameters and technical domain.',
    description,
    tags,
    mark,
    brand,
    url: apiJob.url || '#',
    domain,
    logoUrl,
    matchedSkills,
    missingSkills,
    seniorityFit,
    advice,
    salaryText,
    deadlineText,
    deadlineAt,
  };
}

export type JobFilters = {
  search: string;
  seniority: string;
  location: string;
  minimum: number;
  sort: string;
  shortlistOnly: boolean;
  saved: string[];
};

export function filterJobs(data: Job[], filters: JobFilters) {
  const query = filters.search.toLowerCase().trim();
  return data
    .filter((job) => {
      const textMatch = `${job.company} ${job.title} ${job.location}`.toLowerCase().includes(query);
      const senMatch = filters.seniority === 'all' || job.seniority === filters.seniority;
      const locMatch =
        filters.location === 'all' ||
        job.location.toLowerCase().includes(filters.location.toLowerCase());
      const minMatch = job.score >= filters.minimum;
      const shortlistMatch = !filters.shortlistOnly || filters.saved.includes(job.id);
      return textMatch && senMatch && locMatch && minMatch && shortlistMatch;
    })
    .sort((a, b) =>
      filters.sort === 'recent'
        ? a.daysAgo - b.daysAgo || b.score - a.score
        : b.score - a.score
    );
}

export function scoreBand(score: number): 'excellent' | 'strong' | 'good' | 'fair' | 'low' {
  return score >= 85 ? 'excellent' : score >= 70 ? 'strong' : score >= 55 ? 'good' : score >= 40 ? 'fair' : 'low';
}

export function isNewSince(job: Job, days: number): boolean {
  return job.daysAgo <= days;
}

export type MapAxis = 'technical' | 'domain' | 'reach' | 'location' | 'score';

export const mapAxes: { value: MapAxis; label: string }[] = [
  { value: 'technical', label: 'Technical & experience fit' },
  { value: 'domain', label: 'Company relevance' },
  { value: 'reach', label: 'Achievability' },
  { value: 'location', label: 'Location fit' },
  { value: 'score', label: 'Overall match' },
];

export function isMapAxis(value: string): value is MapAxis {
  return mapAxes.some((a) => a.value === value);
}

export function axisScore(job: Job, axis: MapAxis): number {
  switch (axis) {
    case 'technical':
      return Math.round(((job.breakdown[0] ?? 0) + (job.breakdown[1] ?? 0)) / 2);
    case 'domain':
      return job.breakdown[3] ?? 0;
    case 'reach':
      return job.breakdown[5] ?? 0;
    case 'location':
      return job.breakdown[2] ?? 0;
    case 'score':
      return job.score;
  }
}

export function mapQuadrant(x: number, y: number, threshold = 50): 'sweet' | 'stretch' | 'safety' | 'low' {
  return x >= threshold
    ? y >= threshold
      ? 'sweet'
      : 'safety'
    : y >= threshold
    ? 'stretch'
    : 'low';
}

export function positionMarkers(
  data: Job[],
  xAxis: MapAxis,
  yAxis: MapAxis,
  width: number,
  height: number,
  maxPins = 150
) {
  const placed: { job: Job; x: number; y: number; px: number; py: number; trueX: number; trueY: number }[] = [];
  const slice = data.slice(0, maxPins);

  // Safe area padding to prevent markers from being placed off-screen or under toolbars
  const padLeft = 40;
  const padRight = 65;
  const padTop = 45;
  const padBottom = 80;

  const innerWidth = Math.max(200, width - padLeft - padRight);
  const innerHeight = Math.max(200, height - padTop - padBottom);

  for (const job of slice) {
    const x = axisScore(job, xAxis);
    const y = axisScore(job, yAxis);
    const trueX = padLeft + (x / 100) * innerWidth;
    const trueY = padTop + ((100 - y) / 100) * innerHeight;
    let px = Math.max(padLeft, Math.min(width - padRight, trueX));
    let py = Math.max(padTop, Math.min(height - padBottom, trueY));

    // Avoid initial overlap with the floating top-left Omnibox card (x < 460 && y < 115)
    if (px < 460 && py < 115) {
      py = 125;
    }

    const MIN_DIST = 56;
    const MIN_DIST_SQ = 3136; // 56 * 56

    for (let attempt = 0; attempt < 35; attempt++) {
      let collidesWithPlaced = false;
      for (let i = placed.length - 1; i >= 0; i--) {
        const p = placed[i];
        const dx = p.px - px;
        const dy = p.py - py;
        if (Math.abs(dx) < MIN_DIST && Math.abs(dy) < MIN_DIST) {
          if (dx * dx + dy * dy < MIN_DIST_SQ) {
            collidesWithPlaced = true;
            break;
          }
        }
      }
      const inOmniboxZone = px < 460 && py < 115;
      if (!collidesWithPlaced && !inOmniboxZone) break;

      const angle = attempt * 2.4;
      const radius = 10 * Math.sqrt(attempt + 1);
      px = Math.max(padLeft, Math.min(width - padRight, trueX + Math.cos(angle) * radius));
      py = Math.max(padTop, Math.min(height - padBottom, trueY + Math.sin(angle) * radius));
      if (px < 460 && py < 115) {
        py = 125 + Math.abs(Math.sin(angle)) * 25;
      }
    }
    placed.push({ job, x, y, px, py, trueX, trueY });
  }
  return placed;
}
