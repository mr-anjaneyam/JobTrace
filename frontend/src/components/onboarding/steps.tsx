import { useRef, useState, type DragEvent, type ReactNode } from 'react';
import {
  BellRing,
  Check,
  ChevronDown,
  Eye,
  EyeOff,
  FileText,
  Loader2,
  Radar,
  Send,
  Sparkles,
  UploadCloud,
  Wand2,
} from 'lucide-react';
import { api, type ApiProfile, type TelegramChat } from '@/lib/api';
import { Logo } from '@/components/jobtrace/logo';
import { ChipInput } from './chip-input';
import {
  COUNTRY_OPTIONS,
  LOCATION_SUGGESTIONS,
  PROVIDERS,
  ROLE_SUGGESTIONS,
  SENIORITY_OPTIONS,
  firstName,
  greeting,
  type Draft,
} from './model';

export interface StepProps {
  draft: Draft;
  patch: (p: Partial<Draft>) => void;
}

function StepHead({ eyebrow, title, subtitle }: { eyebrow?: string; title: string; subtitle?: string }) {
  return (
    <header className="ob-head">
      {eyebrow && <span className="ob-eyebrow">{eyebrow}</span>}
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
    </header>
  );
}

function Field({ label, htmlFor, hint, children }: { label: string; htmlFor?: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="ob-field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && <div className="ob-hint">{hint}</div>}
    </div>
  );
}

function SecretInput({
  id,
  value,
  onChange,
  placeholder,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const [shown, setShown] = useState(false);
  return (
    <div className="ob-secret">
      <input
        id={id}
        className="ob-input"
        type={shown ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
      />
      <button type="button" onClick={() => setShown(!shown)} aria-label={shown ? 'Hide' : 'Show'} tabIndex={-1}>
        {shown ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}

export function WelcomeStep() {
  const features = [
    { icon: Radar, title: 'Watches career pages', text: 'Greenhouse, Lever, Ashby, Workday and more.' },
    { icon: Sparkles, title: 'Scores against your resume', text: 'Seniority and location aware, on your machine.' },
    { icon: BellRing, title: 'Pings you on Telegram', text: 'Only when something is worth your time.' },
  ];
  return (
    <div className="ob-welcome">
      <div className="ob-logo-hero">
        <Logo variant="full" size={170} />
      </div>
      <span className="ob-eyebrow">{greeting()}</span>
      <h1 className="ob-hero-title">Your job search, on autopilot</h1>
      <p className="ob-hero-sub">Welcome. Let&apos;s set things up, it takes about two minutes.</p>
      <ul className="ob-features">
        {features.map(({ icon: Icon, title, text }, i) => (
          <li key={title} style={{ ['--i' as string]: i }}>
            <span className="ob-feature-icon">
              <Icon size={18} />
            </span>
            <span>
              <strong>{title}</strong>
              <small>{text}</small>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function NameStep({ draft, patch }: StepProps) {
  return (
    <>
      <StepHead eyebrow="About you" title="What should we call you?" subtitle="A first name is plenty. It stays on this machine." />
      <Field label="Your name" htmlFor="ob-name">
        <input
          id="ob-name"
          className="ob-input ob-input-lg"
          value={draft.name}
          onChange={(e) => patch({ name: e.target.value })}
          placeholder="Ada Lovelace"
          autoFocus
          autoComplete="name"
        />
      </Field>
    </>
  );
}

export function ResumeStep({
  draft,
  profile,
  onUploaded,
}: StepProps & { profile: ApiProfile | null; onUploaded: (profile: ApiProfile | null, filename: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError('');
    try {
      const res = await api.uploadResume(file);
      if (!res.ok) throw new Error(res.error || 'Upload failed');
      onUploaded(res.profile ?? null, file.name);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setBusy(false);
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    void upload(e.dataTransfer.files?.[0]);
  };

  const skills = Array.isArray(profile?.skills) ? profile.skills.slice(0, 6) : [];

  return (
    <>
      <StepHead
        eyebrow="Your resume"
        title="Drop in your resume"
        subtitle="JobTrace reads it locally to understand your skills and seniority. PDF, DOCX, TXT or Markdown, up to 5 MB."
      />
      <input
        ref={inputRef}
        type="file"
        hidden
        accept=".pdf,.docx,.txt,.md"
        onChange={(e) => {
          void upload(e.target.files?.[0]);
          e.target.value = '';
        }}
      />
      {draft.resumeName ? (
        <div className="ob-file-card">
          <span className="ob-file-icon">
            <Check size={18} />
          </span>
          <div className="ob-file-meta">
            <strong>{draft.resumeName}</strong>
            <small>
              {profile?.seniority ? `Looks like ${profile.seniority} level` : 'Resume saved'}
              {skills.length ? ` · ${skills.length}+ skills found` : ''}
            </small>
            {skills.length > 0 && (
              <div className="ob-mini-chips">
                {skills.map((s) => (
                  <span key={s}>{s}</span>
                ))}
              </div>
            )}
          </div>
          <button type="button" className="ob-link" onClick={() => inputRef.current?.click()} disabled={busy}>
            Replace
          </button>
        </div>
      ) : (
        <button
          type="button"
          className={`ob-drop ${over ? 'is-over' : ''} ${busy ? 'is-busy' : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={onDrop}
          disabled={busy}
        >
          <span className="ob-drop-icon">{busy ? <Loader2 size={22} className="animate-spin" /> : <UploadCloud size={22} />}</span>
          <strong>{busy ? 'Reading your resume…' : 'Drag and drop, or browse'}</strong>
          <small>{busy ? 'This only takes a moment' : 'Nothing leaves your machine at this step'}</small>
        </button>
      )}
      {error && <div className="ob-error">{error}</div>}
    </>
  );
}

export function FocusStep({ draft, patch }: StepProps) {
  const who = firstName(draft.name);
  return (
    <>
      <StepHead
        eyebrow={who ? `Nice to meet you, ${who}` : 'Your focus'}
        title="What are you looking for?"
        subtitle="Tune what counts as a match. You can change all of this later."
      />
      <Field label="Role keywords" htmlFor="ob-roles" hint="Openings whose title contains any of these words are kept.">
        <ChipInput id="ob-roles" value={draft.roles} onChange={(roles) => patch({ roles })} suggestions={ROLE_SUGGESTIONS} placeholder="Type a word and press Enter" />
      </Field>
      <Field label="Seniority">
        <div className="ob-segment" style={{ ['--n' as string]: SENIORITY_OPTIONS.length, ['--idx' as string]: SENIORITY_OPTIONS.findIndex((o) => o.value === draft.seniority) }} role="radiogroup" aria-label="Seniority">
          <span className="ob-segment-thumb" />
          {SENIORITY_OPTIONS.map((o) => (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={draft.seniority === o.value}
              className={draft.seniority === o.value ? 'is-on' : ''}
              onClick={() => patch({ seniority: o.value })}
            >
              {o.label}
            </button>
          ))}
        </div>
      </Field>
      <Field label="Locations" htmlFor="ob-locations" hint="Used to rank roles. Leave empty to see everything.">
        <ChipInput id="ob-locations" value={draft.locations} onChange={(locations) => patch({ locations })} suggestions={LOCATION_SUGGESTIONS} placeholder="City or Remote" />
      </Field>
      <Field label="Show jobs in" hint="Picking a country keeps only roles located there and adds companies that hire in it.">
        <div className="ob-segment" style={{ ['--n' as string]: COUNTRY_OPTIONS.length, ['--idx' as string]: Math.max(0, COUNTRY_OPTIONS.findIndex((o) => o.value === draft.country)) }} role="radiogroup" aria-label="Country">
          <span className="ob-segment-thumb" />
          {COUNTRY_OPTIONS.map((o) => (
            <button
              key={o.value || 'any'}
              type="button"
              role="radio"
              aria-checked={draft.country === o.value}
              className={draft.country === o.value ? 'is-on' : ''}
              onClick={() => patch({ country: o.value })}
            >
              {o.label}
            </button>
          ))}
        </div>
        {draft.country && (
          <label className="ob-check-row">
            <input type="checkbox" checked={draft.includeRemote} onChange={(e) => patch({ includeRemote: e.target.checked })} />
            <span>Also keep remote roles that are not tied to a country</span>
          </label>
        )}
      </Field>
    </>
  );
}

export function TelegramStep({ draft, patch }: StepProps) {
  const [guide, setGuide] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [found, setFound] = useState<{ chats: TelegramChat[]; message: string; ok: boolean } | null>(null);
  const [testing, setTesting] = useState(false);
  const [test, setTest] = useState<{ ok: boolean; message: string } | null>(null);

  const token = draft.botToken.trim();

  const detect = async () => {
    setDetecting(true);
    setFound(null);
    try {
      const res = await api.detectTelegramChat(token);
      setFound(res);
      if (res.chats.length === 1 && !draft.chatIds.includes(res.chats[0].id)) {
        patch({ chatIds: [...draft.chatIds, res.chats[0].id] });
      }
    } catch {
      setFound({ ok: false, chats: [], message: 'Could not reach the server.' });
    } finally {
      setDetecting(false);
    }
  };

  const sendTest = async () => {
    setTesting(true);
    setTest(null);
    try {
      setTest(await api.testTelegram({ bot_token: token, chat_ids: draft.chatIds }));
    } catch {
      setTest({ ok: false, message: 'Could not reach the server.' });
    } finally {
      setTesting(false);
    }
  };

  const toggleChat = (id: string) =>
    patch({ chatIds: draft.chatIds.includes(id) ? draft.chatIds.filter((x) => x !== id) : [...draft.chatIds, id] });

  return (
    <>
      <StepHead
        eyebrow="Alerts"
        title="Where should we ping you?"
        subtitle="Get a Telegram message the moment a strong match appears. Prefer not to? Skip it and use the dashboard."
      />
      <Field label="Bot token" htmlFor="ob-token">
        <SecretInput id="ob-token" value={draft.botToken} onChange={(botToken) => patch({ botToken })} placeholder="123456:ABC..." />
      </Field>
      <button type="button" className="ob-disclosure" onClick={() => setGuide(!guide)} aria-expanded={guide}>
        <ChevronDown size={14} className={guide ? 'is-open' : ''} />
        How do I get a token?
      </button>
      {guide && (
        <ol className="ob-guide">
          <li>
            Open <a href="https://t.me/BotFather" target="_blank" rel="noreferrer">@BotFather</a> in Telegram and send <code>/newbot</code>.
          </li>
          <li>Pick a name, then copy the token it gives you into the field above.</li>
          <li>Open your new bot and press <strong>Start</strong>, then use Detect below.</li>
        </ol>
      )}

      <Field label="Chat" htmlFor="ob-chat">
        <div className="ob-row">
          <ChipInput id="ob-chat" value={draft.chatIds} onChange={(chatIds) => patch({ chatIds })} placeholder="Chat ID" />
        </div>
      </Field>
      <div className="ob-actions-row">
        <button type="button" className="ob-btn ob-btn-secondary" onClick={detect} disabled={!token || detecting}>
          {detecting ? <Loader2 size={15} className="animate-spin" /> : <Wand2 size={15} />}
          Detect my chat
        </button>
        <button type="button" className="ob-btn ob-btn-secondary" onClick={sendTest} disabled={!token || draft.chatIds.length === 0 || testing}>
          {testing ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          Send test ping
        </button>
      </div>
      {found && (
        <div className={`ob-note ${found.ok ? '' : 'is-error'}`}>
          {found.message}
          {found.chats.length > 0 && (
            <div className="ob-chat-list">
              {found.chats.map((c) => (
                <button type="button" key={c.id} className={draft.chatIds.includes(c.id) ? 'is-on' : ''} onClick={() => toggleChat(c.id)}>
                  {draft.chatIds.includes(c.id) && <Check size={13} />}
                  {c.name}
                  <small>{c.id}</small>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      {test && <div className={`ob-note ${test.ok ? 'is-ok' : 'is-error'}`}>{test.message}</div>}
    </>
  );
}

export function AiStep({ draft, patch }: StepProps) {
  const current = PROVIDERS.find((p) => p.id === draft.provider) ?? PROVIDERS[0];
  const needsKey = Boolean(current.keyEnv);
  return (
    <>
      <StepHead eyebrow="Scoring" title="How should we judge matches?" subtitle="Pick a scoring engine. Keys are stored only on this machine." />
      <div className="ob-cards" role="radiogroup" aria-label="Scoring engine">
        {PROVIDERS.map((p) => (
          <button
            key={p.id}
            type="button"
            role="radio"
            aria-checked={draft.provider === p.id}
            className={`ob-card ${draft.provider === p.id ? 'is-on' : ''}`}
            onClick={() => patch({ provider: p.id, model: p.defaultModel ?? '', apiKey: '' })}
          >
            <span className="ob-card-top">
              <strong>{p.title}</strong>
              <span className="ob-radio">{draft.provider === p.id && <Check size={11} />}</span>
            </span>
            <small>{p.description}</small>
            {p.badge && <em>{p.badge}</em>}
          </button>
        ))}
      </div>
      {needsKey && (
        <div className="ob-reveal">
          <Field label={`${current.title} API key`} htmlFor="ob-key">
            <SecretInput id="ob-key" value={draft.apiKey} onChange={(apiKey) => patch({ apiKey })} placeholder="sk-..." />
          </Field>
          <Field label="Model" htmlFor="ob-model">
            <input id="ob-model" className="ob-input" value={draft.model} onChange={(e) => patch({ model: e.target.value })} spellCheck={false} />
          </Field>
        </div>
      )}
      {current.id === 'ollama' && (
        <div className="ob-reveal">
          <Field label="Model" htmlFor="ob-model-ollama">
            <input id="ob-model-ollama" className="ob-input" value={draft.model} onChange={(e) => patch({ model: e.target.value })} spellCheck={false} />
          </Field>
        </div>
      )}
    </>
  );
}

export function ReviewStep({ draft, goTo }: { draft: Draft; goTo: (index: number) => void }) {
  const provider = PROVIDERS.find((p) => p.id === draft.provider);
  const rows: { label: string; value: string; step: number }[] = [
    { label: 'Name', value: draft.name.trim() || 'Not set', step: 1 },
    { label: 'Resume', value: draft.resumeName ?? 'Skipped', step: 2 },
    { label: 'Roles', value: draft.roles.join(', ') || 'Any title', step: 3 },
    { label: 'Seniority', value: SENIORITY_OPTIONS.find((o) => o.value === draft.seniority)?.label ?? draft.seniority, step: 3 },
    { label: 'Locations', value: draft.locations.join(', ') || 'Anywhere', step: 3 },
    { label: 'Show jobs in', value: COUNTRY_OPTIONS.find((o) => o.value === draft.country)?.label ?? 'Anywhere', step: 3 },
    { label: 'Telegram', value: draft.botToken.trim() ? `Connected (${draft.chatIds.length || 'no'} chat${draft.chatIds.length === 1 ? '' : 's'})` : 'Skipped', step: 4 },
    { label: 'Scoring', value: provider?.title ?? draft.provider, step: 5 },
  ];
  return (
    <>
      <StepHead
        eyebrow="Almost there"
        title="Ready when you are."
        subtitle="Scanning takes a few minutes and runs in the background. You can close the tab while it works."
      />
      <ul className="ob-summary">
        {rows.map((r) => (
          <li key={r.label}>
            <span>{r.label}</span>
            <strong title={r.value}>{r.value}</strong>
            <button type="button" className="ob-link" onClick={() => goTo(r.step)}>
              Edit
            </button>
          </li>
        ))}
      </ul>
      <p className="ob-fineprint">
        <FileText size={13} /> Everything is stored locally in your JobTrace data folder.
      </p>
    </>
  );
}
