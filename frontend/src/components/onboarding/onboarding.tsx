import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowLeft, ArrowRight, Loader2 } from 'lucide-react';
import { api, type ApiProfile, type SettingsUpdate } from '@/lib/api';
import { Logo } from '@/components/jobtrace/logo';
import { AiStep, FocusStep, NameStep, ResumeStep, ReviewStep, TelegramStep, WelcomeStep } from './steps';
import { ProgressScreen } from './progress-screen';
import { PROVIDERS, SENIORITY_OPTIONS, defaultDraft, type Draft, type Seniority } from './model';
import '@/onboarding.css';

const LAST = 6;
const EXIT_MS = 170;

const ROLE_HINTS = ['backend', 'frontend', 'full stack', 'devops', 'data', 'machine learning', 'mobile'];

function rolesFromProfile(p: ApiProfile, base: string[]): string[] {
  const skills = Array.isArray(p.skills) ? p.skills.join(' ') : p.skills ?? '';
  const haystack = `${p.headline ?? ''} ${skills}`.toLowerCase();
  const extra = ROLE_HINTS.filter((h) => haystack.includes(h) && !base.includes(h));
  return [...base, ...extra];
}

export function ResumedProgress({ name, onOpenDashboard }: { name: string; onOpenDashboard: () => void }) {
  return (
    <div className="ob-root">
      <div className="ob-bg" aria-hidden="true" />
      <header className="ob-top">
        <div className="ob-brand">
          <Logo size={26} />
          <span>JobTrace</span>
        </div>
      </header>
      <main className="ob-main">
        <ProgressScreen name={name} onOpenDashboard={onOpenDashboard} />
      </main>
    </div>
  );
}

export function Onboarding({ onOpenDashboard }: { onOpenDashboard: () => void }) {
  const [step, setStep] = useState(0);
  const [phase, setPhase] = useState<'in' | 'out'>('in');
  const [dir, setDir] = useState<1 | -1>(1);
  const [draft, setDraft] = useState<Draft>(defaultDraft);
  const [profile, setProfile] = useState<ApiProfile | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [started, setStarted] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    rootRef.current?.scrollTo({ top: 0 });
  }, [step, started]);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const patch = (p: Partial<Draft>) => setDraft((d) => ({ ...d, ...p }));

  const go = (next: number) => {
    if (next === step || phase === 'out' || next < 0 || next > LAST) return;
    setDir(next > step ? 1 : -1);
    setPhase('out');
    timer.current = setTimeout(() => {
      setStep(next);
      setPhase('in');
    }, EXIT_MS);
  };

  const applyProfile = (p: ApiProfile | null, filename: string) => {
    setProfile(p);
    setDraft((d) => {
      const next: Draft = { ...d, resumeName: filename };
      if (!d.name.trim() && p?.name) next.name = p.name;
      const sen = p?.seniority as Seniority | undefined;
      if (sen && SENIORITY_OPTIONS.some((o) => o.value === sen)) next.seniority = sen;
      if (p?.target_locations?.length) next.locations = p.target_locations;
      if (p) next.roles = rolesFromProfile(p, d.roles);
      return next;
    });
  };

  const provider = PROVIDERS.find((p) => p.id === draft.provider);
  const needsKey = Boolean(provider?.keyEnv) && !draft.apiKey.trim();

  const submit = async () => {
    setSubmitting(true);
    setError('');
    try {
      const settings: SettingsUpdate = {
        candidate: { seniority: draft.seniority, locations: draft.locations },
        filters: { title_include: draft.roles, country: draft.country, include_remote: draft.includeRemote },
        llm: { provider: draft.provider, ...(provider?.defaultModel && draft.model.trim() ? { model: draft.model.trim() } : {}) },
      };
      if (draft.botToken.trim()) settings.telegram = { bot_token: draft.botToken.trim(), chat_ids: draft.chatIds };
      if (provider?.keyEnv && draft.apiKey.trim()) settings.api_keys = { [provider.keyEnv]: draft.apiKey.trim() };

      const saved = await api.updateSettings(settings);
      if (!saved.ok) throw new Error(saved.message || 'Could not save your settings.');
      await api.completeOnboarding(draft.name.trim());
      setStarted(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    if (step === LAST) void submit();
    else go(step + 1);
  };

  const label =
    step === 0
      ? 'Get started'
      : step === 2 && !draft.resumeName
      ? 'Skip for now'
      : step === 4 && !draft.botToken.trim()
      ? 'Skip for now'
      : step === LAST
      ? 'Start scanning'
      : 'Continue';
  const disabled = (step === 1 && !draft.name.trim()) || (step === 5 && needsKey) || submitting;

  const header = (
    <header className="ob-top">
      <div className="ob-brand">
        <Logo size={26} />
        <span>JobTrace</span>
      </div>
      {step > 0 && !started && (
        <div className="ob-steps" aria-label={`Step ${step} of ${LAST}`}>
          {Array.from({ length: LAST }, (_, i) => (
            <span key={i} className={i < step ? 'is-done' : i === step - 1 ? 'is-current' : ''} />
          ))}
        </div>
      )}
    </header>
  );

  if (started) {
    return (
      <div className="ob-root" ref={rootRef}>
        <div className="ob-bg" aria-hidden="true" />
        {header}
        <main className="ob-main">
          <ProgressScreen name={draft.name} onOpenDashboard={onOpenDashboard} />
        </main>
      </div>
    );
  }

  return (
    <div className="ob-root" ref={rootRef}>
      <div className="ob-bg" aria-hidden="true" />
      {header}
      <main className="ob-main">
        <form className="ob-panel" onSubmit={onSubmit} noValidate>
          <div className="ob-stage" data-phase={phase} data-dir={dir} key={step}>
            {step === 0 && <WelcomeStep />}
            {step === 1 && <NameStep draft={draft} patch={patch} />}
            {step === 2 && <ResumeStep draft={draft} patch={patch} profile={profile} onUploaded={applyProfile} />}
            {step === 3 && <FocusStep draft={draft} patch={patch} />}
            {step === 4 && <TelegramStep draft={draft} patch={patch} />}
            {step === 5 && <AiStep draft={draft} patch={patch} />}
            {step === 6 && <ReviewStep draft={draft} goTo={go} />}
            {error && step === LAST && <div className="ob-error">{error}</div>}
          </div>

          <div className={`ob-footer ${step === 0 ? 'is-welcome' : ''}`}>
            {step > 0 && (
              <button type="button" className="ob-btn ob-btn-ghost" onClick={() => go(step - 1)} disabled={submitting}>
                <ArrowLeft size={15} /> Back
              </button>
            )}
            <button type="submit" className={`ob-btn ob-btn-primary ${step === 0 ? 'ob-btn-lg' : ''}`} disabled={disabled}>
              {submitting ? <Loader2 size={16} className="animate-spin" /> : null}
              {label}
              {!submitting && <ArrowRight size={16} />}
            </button>
          </div>
          {step === 0 && <p className="ob-fineprint ob-center">Takes about two minutes. Everything stays on your machine.</p>}
        </form>
      </main>
    </div>
  );
}
