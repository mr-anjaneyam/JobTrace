export interface ApiJob {
  id: string;
  company: string;
  title: string;
  url: string;
  location: string;
  score: number | null;
  reason: string;
  domain: string;
  source: string;
  breakdown?: string | Record<string, number>;
  first_seen?: number;
  posted_at?: number;
  description?: string;
  closed_at?: number | null;
}

export interface ApiStateResponse {
  jobs: ApiJob[];
  companies: string[];
  stats: {
    checked: number;
    total: number;
    closed: number;
    would_apply: number;
    avg: number;
    threshold: number;
  };
  scanning: boolean;
  scoring: boolean;
}

export interface ApiProfile {
  name?: string;
  headline?: string;
  location?: string;
  seniority?: string;
  seniority_reason?: string;
  target_locations?: string[];
  skills?: string[] | string;
  experience?: Array<{
    title?: string;
    company?: string;
    duration?: string;
    highlights?: string[] | string;
    role?: string;
    org?: string;
    years?: string;
  }>;
  education?: Array<{
    degree?: string;
    institution?: string;
    year?: string;
  }>;
  summary?: string;
  years_experience?: number;
  years_of_experience?: number;
  error?: string;
}

export interface ApiSettings {
  telegram: {
    bot_token: string;
    chat_ids: string[];
    chat_ids_raw: string;
  };
  llm: {
    provider: string;
    model: string;
    min_score: number;
    triage: boolean;
  };
  candidate: {
    seniority: string;
    locations: string[];
  };
  resume_path?: string;
  api_keys: Record<string, string>;
}

export interface SettingsUpdate {
  telegram?: { bot_token?: string; chat_ids?: string[] | string };
  llm?: { provider?: string; model?: string; min_score?: number; triage?: boolean };
  candidate?: { seniority?: string; locations?: string[] };
  filters?: { title_include?: string[] };
  api_keys?: Record<string, string>;
}

export interface OnboardingScan {
  state: 'idle' | 'running' | 'done' | 'error';
  percent: number;
  message: string;
  new: number;
  scored: number;
  errors: string[];
  note: string;
}

export interface OnboardingStatus {
  completed: boolean;
  name: string;
  scan: OnboardingScan;
}

export interface TelegramChat {
  id: string;
  name: string;
  type: string;
}

export const api = {
  async getState(): Promise<ApiStateResponse> {
    const res = await fetch('/api/state');
    if (!res.ok) throw new Error(`HTTP ${res.status} fetching state`);
    return res.json();
  },

  async search(query: string, signal?: AbortSignal): Promise<string[] | null> {
    const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`, { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status} searching jobs`);
    const data: { ids: string[] | null } = await res.json();
    return data.ids;
  },

  async getOnboardingStatus(): Promise<OnboardingStatus> {
    const res = await fetch('/api/onboarding/status');
    if (!res.ok) throw new Error(`HTTP ${res.status} fetching onboarding status`);
    return res.json();
  },

  async completeOnboarding(name: string, startScan = true): Promise<{ ok: boolean; started: boolean; scan: OnboardingScan }> {
    const res = await fetch('/api/onboarding/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, start_scan: startScan }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} completing onboarding`);
    return res.json();
  },

  async detectTelegramChat(botToken: string): Promise<{ ok: boolean; chats: TelegramChat[]; message: string }> {
    const res = await fetch('/api/telegram/detect-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_token: botToken }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} detecting chat`);
    return res.json();
  },

  async getJobDetail(id: string): Promise<ApiJob> {
    const res = await fetch(`/api/jobs/${encodeURIComponent(id)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status} fetching job detail`);
    return res.json();
  },

  async getProfile(): Promise<ApiProfile> {
    const res = await fetch('/api/profile');
    if (!res.ok) throw new Error(`HTTP ${res.status} fetching profile`);
    return res.json();
  },

  async updateProfile(profile: Partial<ApiProfile>): Promise<{ ok: boolean; message?: string }> {
    const res = await fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} updating profile`);
    return res.json();
  },

  async uploadResume(file: File): Promise<{ ok: boolean; filename?: string; profile?: ApiProfile; error?: string }> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/upload-resume', {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} uploading resume`);
    return res.json();
  },

  async getSettings(): Promise<ApiSettings> {
    const res = await fetch('/api/settings');
    if (!res.ok) throw new Error(`HTTP ${res.status} fetching settings`);
    return res.json();
  },

  async updateSettings(settings: SettingsUpdate): Promise<{ ok: boolean; message?: string }> {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} updating settings`);
    return res.json();
  },

  async testTelegram(payload: { bot_token?: string; chat_ids?: string[] }): Promise<{ ok: boolean; message: string }> {
    const res = await fetch('/api/test-telegram', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} testing telegram`);
    return res.json();
  },

  async verifyJob(id: string): Promise<{ ok: boolean; active: boolean; reason: string; url?: string }> {
    const res = await fetch(`/api/jobs/${encodeURIComponent(id)}/verify`);
    if (!res.ok) throw new Error(`HTTP ${res.status} verifying job`);
    return res.json();
  },

  async discardJob(id: string): Promise<{ ok: boolean; job_id?: string; message?: string }> {
    const res = await fetch(`/api/jobs/${encodeURIComponent(id)}/discard`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} discarding job`);
    return res.json();
  },

  async discardClosedJobs(): Promise<{ ok: boolean; total_closed: number; elapsed_count: number; archived_count: number; closed: any[] }> {
    const res = await fetch('/api/jobs/discard-closed', {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} running discard-closed`);
    return res.json();
  },

  createScanEventSource(
    onMessage: (data: any) => void,
    onError: (err: any) => void,
    onComplete: () => void
  ): () => void {
    const ev = new EventSource('/api/scan');
    ev.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        onMessage(parsed);
      } catch {
        // Raw text
      }
    };
    ev.onerror = (err) => {
      ev.close();
      onError(err);
      onComplete();
    };
    return () => ev.close();
  },
};
