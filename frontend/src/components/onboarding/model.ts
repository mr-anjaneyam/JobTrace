export type Seniority = 'intern' | 'junior' | 'mid' | 'senior' | 'lead' | 'any';

export interface Draft {
  name: string;
  resumeName: string | null;
  roles: string[];
  seniority: Seniority;
  locations: string[];
  country: string;
  includeRemote: boolean;
  botToken: string;
  chatIds: string[];
  provider: string;
  model: string;
  apiKey: string;
}

export const SENIORITY_OPTIONS: { value: Seniority; label: string }[] = [
  { value: 'intern', label: 'Intern' },
  { value: 'junior', label: 'Junior' },
  { value: 'mid', label: 'Mid' },
  { value: 'senior', label: 'Senior' },
  { value: 'lead', label: 'Lead' },
  { value: 'any', label: 'Any' },
];

export const ROLE_SUGGESTIONS = [
  'engineer',
  'developer',
  'backend',
  'frontend',
  'full stack',
  'data',
  'machine learning',
  'devops',
  'mobile',
  'product',
  'designer',
  'analyst',
  'intern',
];

export const LOCATION_SUGGESTIONS = ['Remote', 'Bengaluru', 'London', 'New York', 'San Francisco', 'Berlin'];

export const COUNTRY_OPTIONS = [
  { value: '', label: 'Anywhere' },
  { value: 'india', label: 'India' },
];

export interface ProviderOption {
  id: string;
  title: string;
  description: string;
  badge?: string;
  keyEnv?: string;
  defaultModel?: string;
}

export const PROVIDERS: ProviderOption[] = [
  {
    id: 'local',
    title: 'Offline matcher',
    description: 'Free and private. Matches skills, seniority and location on your machine.',
    badge: 'No key needed',
  },
  {
    id: 'openai',
    title: 'OpenAI',
    description: 'Highest quality scoring with your own API key.',
    keyEnv: 'OPENAI_API_KEY',
    defaultModel: 'gpt-4o-mini',
  },
  {
    id: 'openrouter',
    title: 'OpenRouter',
    description: 'One key, hundreds of models.',
    keyEnv: 'OPENROUTER_API_KEY',
    defaultModel: 'openai/gpt-4o-mini',
  },
  {
    id: 'xkiro',
    title: 'xkiro',
    description: 'Mistral Large, the project default.',
    keyEnv: 'XKIRO_API_KEY',
    defaultModel: 'mistralai/mistral-large-2512',
  },
  {
    id: 'ollama',
    title: 'Ollama',
    description: 'Runs on your own machine. Needs Ollama running locally (Docker reaches it via the host).',
    badge: 'No key needed',
    defaultModel: 'llama3.1',
  },
  {
    id: 'none',
    title: 'No scoring yet',
    description: 'Just collect openings. Turn scoring on later in Settings.',
  },
];

export const defaultDraft = (): Draft => ({
  name: '',
  resumeName: null,
  roles: ['engineer', 'developer'],
  seniority: 'junior',
  locations: ['Remote'],
  country: '',
  includeRemote: false,
  botToken: '',
  chatIds: [],
  provider: 'local',
  model: '',
  apiKey: '',
});

export function greeting(now = new Date()): string {
  const h = now.getHours();
  if (h < 5) return 'Hello';
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

export const firstName = (full: string) => full.trim().split(/\s+/)[0] ?? '';
