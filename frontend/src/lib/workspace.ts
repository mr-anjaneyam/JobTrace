export type WorkspaceState = {
  search: string;
  seniority: string;
  location: string;
  source: string;
  minimum: number;
  saved: string[];
  shortlistOnly: boolean;
  xAxis: string;
  yAxis: string;
  threshold: number;
  lastVisit: number;
};

export const WORKSPACE_KEY = 'jobtrace.workspace.v2';

export function defaultWorkspace(now = Date.now()): WorkspaceState {
  return {
    search: '',
    seniority: 'all',
    location: 'all',
    source: 'all',
    minimum: 0,
    saved: [],
    shortlistOnly: false,
    xAxis: 'technical',
    yAxis: 'domain',
    threshold: 50,
    lastVisit: now,
  };
}

export function loadWorkspace(): Partial<WorkspaceState> | null {
  try {
    const raw = localStorage.getItem(WORKSPACE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<WorkspaceState>;
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveWorkspace(state: WorkspaceState) {
  try {
    localStorage.setItem(WORKSPACE_KEY, JSON.stringify(state));
  } catch {
    // Ignore quota or private browsing errors
  }
}
