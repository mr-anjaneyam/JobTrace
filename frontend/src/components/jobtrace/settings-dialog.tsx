import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api, type ApiSettings } from '@/lib/api';
import { Settings, Send, Check, AlertCircle, Key, Cpu, Bell, Eye, EyeOff } from 'lucide-react';

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

  useEffect(() => {
    if (open) {
      loadSettings();
    }
  }, [open]);

  const loadSettings = async () => {
    setLoading(true);
    setStatusMsg(null);
    setTestResult(null);
    try {
      const data = await api.getSettings();
      setSettings(data);
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
      await api.updateSettings(settings);
      setStatusMsg({ type: 'success', text: 'Settings saved successfully!' });
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
              <p className="text-xs text-muted-foreground">Manage Telegram alerts, AI scoring model, and API keys.</p>
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
                      placeholder="123456789:ABCdefGHI..."
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
                    placeholder="987654321, 123456789"
                    className="h-8 text-xs font-mono"
                  />
                </div>
              </div>
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
