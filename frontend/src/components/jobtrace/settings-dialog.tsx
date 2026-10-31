import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api, type ApiSettings } from '@/lib/api';
import { COUNTRY_OPTIONS } from '@/components/onboarding/model';
import { Settings, Send, Check, AlertCircle, Key, Cpu, Bell, Eye, EyeOff, MapPin, Gauge, ScrollText } from 'lucide-react';

const compact = (n: number) => (n >= 1e6 ? `${+(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}k` : String(n));
const splitList = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean);

function NumField({
  label,
  value,
  onChange,
  min,
  max,
  hint,
  blankLabel,
}: {
  label: string;
  value: number | null;
  onChange: (n: number | null) => void;
  min: number;
  max: number;
  hint?: string;
  blankLabel?: string;
}) {
  const show = (v: number | null) => (v == null ? '' : String(v));
  const [text, setText] = useState(show(value));
  useEffect(() => setText(show(value)), [value]);
  return (
    <div>
      <label className="text-muted-foreground mb-1 block">{label}</label>
      <Input
        type="number"
        min={min}
        max={max}
        value={text}
        placeholder={blankLabel}
        onChange={(e) => {
          setText(e.target.value);
          if (e.target.value === '' && blankLabel) onChange(null);
          else if (e.target.value !== '' && Number.isFinite(Number(e.target.value))) onChange(Number(e.target.value));
        }}
        onBlur={() => setText(show(value))}
        className="h-8 text-xs font-mono"
      />
      {hint && <p className="text-[11px] text-muted-foreground mt-1">{hint}</p>}
    </div>
  );
}

export function SettingsDialog({
  open,
  onOpenChange,
  onSettingsUpdated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSettingsUpdated?: () => void;
}) {
  const [settings, setSettings] = useState<ApiSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showTokens, setShowTokens] = useState<Record<string, boolean>>({});
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [rolesText, setRolesText] = useState('');
  const [excludeText, setExcludeText] = useState('');

  useEffect(() => {
    if (open) {
      loadSettings();
    }
  }, [open]);

  const adopt = (data: ApiSettings) => {
    setSettings(data);
    setRolesText(data.filters.title_include.join(', '));
    setExcludeText(data.filters.title_exclude.join(', '));
  };

  const loadSettings = async () => {
    setLoading(true);
    setStatusMsg(null);
    setTestResult(null);
    try {
      adopt(await api.getSettings());
    } catch (e: any) {
      setStatusMsg({ type: 'error', text: e.message || 'Failed to load settings' });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setStatusMsg(null);
    try {
      const saved = await api.updateSettings({
        ...settings,
        filters: { ...settings.filters, title_include: splitList(rolesText), title_exclude: splitList(excludeText) },
      });
      const added = saved.added_companies?.length ?? 0;
      setStatusMsg({
        type: 'success',
        text: added
          ? `Settings saved. Added ${added} companies; run a scan to fetch their roles.`
          : 'Settings saved. Changes apply from the next scan.',
      });
      // Show what the server actually stored (values are clamped to safe ranges)
      api.getSettings().then(adopt).catch(() => undefined);
      if (onSettingsUpdated) onSettingsUpdated();
    } catch (e: any) {
      setStatusMsg({ type: 'error', text: e.message || 'Failed to save settings' });
    } finally {
      setSaving(false);
    }
  };

  const handleTestTelegram = async () => {
    if (!settings) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.testTelegram({
        bot_token: settings.telegram.bot_token,
        chat_ids: settings.telegram.chat_ids,
      });
      setTestResult(res);
    } catch (e: any) {
      setTestResult({ ok: false, message: e.message || 'Connection test failed' });
    } finally {
      setTesting(false);
    }
  };

  const toggleShow = (key: string) => {
    setShowTokens((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[88vh] overflow-y-auto p-6">
        <DialogTitle className="sr-only">Configuration Settings</DialogTitle>
        <div className="flex items-center justify-between pb-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-full bg-secondary flex items-center justify-center text-primary font-display font-semibold">
              <Settings size={20} />
            </div>
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Configuration Settings</h2>
              <p className="text-xs text-muted-foreground">Manage Telegram alerts, job search, AI scoring, token budget and API keys.</p>
            </div>
          </div>
          <Button size="sm" onClick={handleSave} disabled={saving || loading}>
            {saving ? 'Saving...' : 'Save Settings'}
          </Button>
        </div>

        {statusMsg && (
          <div
            className={`p-3 rounded-md text-xs flex items-center gap-2 ${
              statusMsg.type === 'success'
                ? 'bg-secondary text-primary border border-primary/20'
                : 'bg-destructive/10 text-destructive border border-destructive/20'
            }`}
          >
            {statusMsg.type === 'success' ? <Check size={14} /> : <AlertCircle size={14} />}
            {statusMsg.text}
          </div>
        )}

        {loading ? (
          <div className="py-12 text-center text-muted-foreground text-sm">Loading configuration...</div>
        ) : settings ? (
          <div className="space-y-6 pt-2">
            {/* Telegram Section */}
            <div className="rounded-lg border border-border p-4 bg-card space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-medium text-sm">
                  <Bell size={16} className="text-primary" />
                  <span>Telegram Alerts</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleTestTelegram}
                  disabled={testing || !settings.telegram.bot_token}
                  className="text-xs h-7"
                >
                  <Send size={12} />
                  {testing ? 'Testing...' : 'Test Ping'}
                </Button>
              </div>

              {testResult && (
                <div
                  className={`p-2.5 rounded text-xs flex items-center gap-2 ${
                    testResult.ok
                      ? 'bg-secondary text-primary border border-primary/20'
                      : 'bg-destructive/10 text-destructive border border-destructive/20'
                  }`}
                >
                  {testResult.ok ? <Check size={13} /> : <AlertCircle size={13} />}
                  {testResult.message}
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="text-muted-foreground mb-1 block">Bot Token</label>
                  <div className="relative">
                    <Input
                      type={showTokens['tg'] ? 'text' : 'password'}
                      value={settings.telegram.bot_token || ''}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          telegram: { ...settings.telegram, bot_token: e.target.value },
                        })
                      }
                      placeholder="123456:ABCdef..."
                      className="h-8 text-xs font-mono pr-8"
                    />
                    <button
                      type="button"
                      onClick={() => toggleShow('tg')}
                      className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                    >
                      {showTokens['tg'] ? <EyeOff size={13} /> : <Eye size={13} />}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="text-muted-foreground mb-1 block">Recipient Chat IDs</label>
                  <Input
                    value={settings.telegram.chat_ids_raw || settings.telegram.chat_ids.join(', ')}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        telegram: {
                          ...settings.telegram,
                          chat_ids_raw: e.target.value,
                          chat_ids: e.target.value
                            .split(',')
                            .map((s) => s.trim())
                            .filter(Boolean),
                        },
                      })
                    }
                    placeholder="1234567, 8901234"
                    className="h-8 text-xs font-mono"
                  />
                </div>
              </div>
            </div>

            {/* Job search */}
            <div className="rounded-lg border border-border p-4 bg-card space-y-3">
              <div className="flex items-center gap-2 font-medium text-sm">
                <MapPin size={16} className="text-primary" />
                <span>Job Search</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="text-muted-foreground mb-1 block">Show jobs in</label>
                  <select
                    value={settings.filters.country}
                    onChange={(e) => setSettings({ ...settings, filters: { ...settings.filters, country: e.target.value } })}
                    className="flex h-8 w-full rounded-md border border-input bg-transparent px-2.5 py-1 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    {COUNTRY_OPTIONS.map((o) => (
                      <option key={o.value || 'any'} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                {settings.filters.country ? (
                  <label className="flex items-center gap-2 text-muted-foreground cursor-pointer sm:pt-5">
                    <input
                      type="checkbox"
                      checked={settings.filters.include_remote}
                      onChange={(e) => setSettings({ ...settings, filters: { ...settings.filters, include_remote: e.target.checked } })}
                      className="rounded border-border text-primary focus:ring-primary size-4"
                    />
                    <span>Also keep remote roles not tied to a country</span>
                  </label>
                ) : null}
                <div>
                  <label className="text-muted-foreground mb-1 block">Role keywords (title contains any)</label>
                  <Input value={rolesText} onChange={(e) => setRolesText(e.target.value)} placeholder="engineer, developer" className="h-8 text-xs" />
                </div>
                <div>
                  <label className="text-muted-foreground mb-1 block">Skip titles containing</label>
                  <Input value={excludeText} onChange={(e) => setExcludeText(e.target.value)} placeholder="director, manager" className="h-8 text-xs" />
                </div>
              </div>
              <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.discovery.enabled}
                  onChange={(e) => setSettings({ ...settings, discovery: { enabled: e.target.checked } })}
                  className="rounded border-border text-primary focus:ring-primary size-4"
                />
                <span>Also search remote job feeds (Remotive, Arbeitnow)</span>
              </label>
              <p className="text-[11px] text-muted-foreground">
                Takes effect on the next scan. Choosing a country also adds companies that hire there.
              </p>
            </div>

            {/* AI Scoring Engine */}
            <div className="rounded-lg border border-border p-4 bg-card space-y-4">
              <div className="flex items-center gap-2 font-medium text-sm">
                <Cpu size={16} className="text-primary" />
                <span>AI Scoring Engine</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <label className="text-muted-foreground mb-1 block">Provider</label>
                  <select
                    value={settings.llm.provider || 'xkiro'}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        llm: { ...settings.llm, provider: e.target.value },
                      })
                    }
                    className="flex h-8 w-full rounded-md border border-input bg-transparent px-2.5 py-1 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value="xkiro">Xkiro (Mistral Large)</option>
                    <option value="openrouter">OpenRouter</option>
                    <option value="openai">OpenAI</option>
                    <option value="cursor">Cursor Local</option>
                    <option value="ollama">Ollama (Local)</option>
                    <option value="none">Offline Heuristics</option>
                  </select>
                </div>
                <div>
                  <label className="text-muted-foreground mb-1 block">Model</label>
                  <Input
                    value={settings.llm.model || ''}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        llm: { ...settings.llm, model: e.target.value },
                      })
                    }
                    placeholder="mistralai/mistral-large-2512"
                    className="h-8 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="text-muted-foreground mb-1 block">Min Alert Score (1-10)</label>
                  <Input
                    type="number"
                    min={1}
                    max={10}
                    value={settings.llm.min_score ?? 6}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        llm: { ...settings.llm, min_score: Number(e.target.value) },
                      })
                    }
                    className="h-8 text-xs font-mono"
                  />
                </div>
              </div>

              <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer pt-1">
                <input
                  type="checkbox"
                  checked={settings.llm.triage}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      llm: { ...settings.llm, triage: e.target.checked },
                    })
                  }
                  className="rounded border-border text-primary focus:ring-primary size-4"
                />
                <span>Enable Free Triage (filters obvious non-matches before calling LLM APIs)</span>
              </label>
            </div>

            {/* Budget and limits */}
            <div className="rounded-lg border border-border p-4 bg-card space-y-4">
              <div className="flex items-center gap-2 font-medium text-sm">
                <Gauge size={16} className="text-primary" />
                <span>Budget &amp; Limits</span>
              </div>

              <div>
                <div className="flex justify-between text-[11px] text-muted-foreground mb-1">
                  <span>Tokens used today (UTC)</span>
                  <span className="font-mono">
                    {compact(settings.usage.tokens_today)} of {compact(settings.llm.daily_token_limit)}
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${Math.min(100, (settings.usage.tokens_today / Math.max(1, settings.llm.daily_token_limit)) * 100)}%` }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <NumField
                  label="Daily token limit"
                  value={settings.llm.daily_token_limit}
                  min={1000}
                  max={1000000000}
                  onChange={(n) => n != null && setSettings({ ...settings, llm: { ...settings.llm, daily_token_limit: n } })}
                  hint="Scoring stops for the day at this total."
                />
                <NumField
                  label="Max jobs scored per scan"
                  value={settings.llm.max_to_score}
                  min={1}
                  max={100000}
                  onChange={(n) => n != null && setSettings({ ...settings, llm: { ...settings.llm, max_to_score: n } })}
                />
                <NumField
                  label="Jobs per request"
                  value={settings.llm.batch_size}
                  min={1}
                  max={100}
                  onChange={(n) => n != null && setSettings({ ...settings, llm: { ...settings.llm, batch_size: n } })}
                />
                <NumField
                  label="Tokens per request (estimate)"
                  value={settings.llm.tokens_per_batch}
                  min={500}
                  max={100000}
                  onChange={(n) => n != null && setSettings({ ...settings, llm: { ...settings.llm, tokens_per_batch: n } })}
                  hint="Used to plan how many jobs fit the budget."
                />
                <NumField
                  label="Free triage cutoff (0-10)"
                  value={settings.llm.triage_floor}
                  min={0}
                  max={10}
                  onChange={(n) => n != null && setSettings({ ...settings, llm: { ...settings.llm, triage_floor: n } })}
                  hint="Only used when triage is on."
                />
              </div>

              <div className="border-t border-border pt-3 grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
                <NumField
                  label="Alert min score"
                  value={settings.alerts.min_score}
                  min={0}
                  max={10}
                  blankLabel="same as above"
                  onChange={(n) => setSettings({ ...settings, alerts: { ...settings.alerts, min_score: n } })}
                />
                <NumField
                  label="Jobs per alert"
                  value={settings.alerts.max_per_alert}
                  min={1}
                  max={50}
                  onChange={(n) => n != null && setSettings({ ...settings, alerts: { ...settings.alerts, max_per_alert: n } })}
                />
                <NumField
                  label="Jobs per weekly digest"
                  value={settings.digest.max_jobs}
                  min={1}
                  max={200}
                  onChange={(n) => n != null && setSettings({ ...settings, digest: { max_jobs: n } })}
                />
                <NumField
                  label="Keep closed jobs (days)"
                  value={settings.storage.retention_days}
                  min={0}
                  max={3650}
                  hint="0 keeps everything."
                  onChange={(n) => n != null && setSettings({ ...settings, storage: { retention_days: n } })}
                />
              </div>
            </div>

            {/* Logs */}
            <div className="rounded-lg border border-border p-4 bg-card space-y-3">
              <div className="flex items-center gap-2 font-medium text-sm">
                <ScrollText size={16} className="text-primary" />
                <span>Logs</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <label className="text-muted-foreground mb-1 block">Detail</label>
                  <select
                    value={settings.logging.level}
                    onChange={(e) => setSettings({ ...settings, logging: { ...settings.logging, level: e.target.value } })}
                    className="flex h-8 w-full rounded-md border border-input bg-transparent px-2.5 py-1 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    {['DEBUG', 'INFO', 'WARNING', 'ERROR'].map((lvl) => (
                      <option key={lvl} value={lvl}>
                        {lvl}
                      </option>
                    ))}
                  </select>
                </div>
                <NumField
                  label="Keep daily logs (days)"
                  value={settings.logging.retention_days}
                  min={1}
                  max={365}
                  onChange={(n) => n != null && setSettings({ ...settings, logging: { ...settings.logging, retention_days: n } })}
                />
                <NumField
                  label="Max text per request (chars)"
                  value={settings.logging.max_body_chars}
                  min={0}
                  max={100000}
                  hint="0 records no request or response text."
                  onChange={(n) => n != null && setSettings({ ...settings, logging: { ...settings.logging, max_body_chars: n } })}
                />
              </div>
              <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.logging.log_bodies}
                  onChange={(e) => setSettings({ ...settings, logging: { ...settings.logging, log_bodies: e.target.checked } })}
                  className="rounded border-border text-primary focus:ring-primary size-4"
                />
                <span>Record what is sent to and received from job portals and AI models</span>
              </label>
              <p className="text-[11px] text-muted-foreground">
                Files live in the logs folder: jobtrace.log (continuous) and one file per day in logs/daily. Keys are removed, but
                requests can include your resume and job text, so keep that folder private.
              </p>
            </div>

            {/* API Keys */}
            <div className="rounded-lg border border-border p-4 bg-card space-y-3">
              <div className="flex items-center gap-2 font-medium text-sm">
                <Key size={16} className="text-primary" />
                <span>API Keys</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                {['XKIRO_API_KEY', 'OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'CURSOR_API_KEY', 'ANTHROPIC_API_KEY'].map(
                  (keyName) => (
                    <div key={keyName}>
                      <label className="text-muted-foreground mb-1 block font-mono text-[11px]">{keyName}</label>
                      <div className="relative">
                        <Input
                          type={showTokens[keyName] ? 'text' : 'password'}
                          value={settings.api_keys[keyName] || ''}
                          onChange={(e) =>
                            setSettings({
                              ...settings,
                              api_keys: { ...settings.api_keys, [keyName]: e.target.value },
                            })
                          }
                          placeholder="sk-..."
                          className="h-8 text-xs font-mono pr-8"
                        />
                        <button
                          type="button"
                          onClick={() => toggleShow(keyName)}
                          className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                        >
                          {showTokens[keyName] ? <EyeOff size={13} /> : <Eye size={13} />}
                        </button>
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
