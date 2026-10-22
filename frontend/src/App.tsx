import { useEffect, useState } from 'react';
import { Dashboard } from '@/components/jobtrace/dashboard';
import { Logo } from '@/components/jobtrace/logo';
import { Onboarding, ResumedProgress } from '@/components/onboarding/onboarding';
import { api } from '@/lib/api';

type View = 'loading' | 'onboarding' | 'progress' | 'dashboard';

const SKIP_KEY = 'jt.skipProgress';

export function App() {
  const path = typeof window !== 'undefined' ? window.location.pathname : '/';
  const [view, setView] = useState<View>('loading');
  const [name, setName] = useState('');

  useEffect(() => {
    let alive = true;
    api
      .getOnboardingStatus()
      .then((status) => {
        if (!alive) return;
        setName(status.name);
        if (path === '/welcome' || !status.completed) setView('onboarding');
        else if (status.scan.state === 'running' && !sessionStorage.getItem(SKIP_KEY)) setView('progress');
        else setView('dashboard');
      })
      .catch(() => alive && setView('dashboard'));
    return () => {
      alive = false;
    };
  }, [path]);

  const openDashboard = () => {
    sessionStorage.setItem(SKIP_KEY, '1');
    if (window.location.pathname === '/welcome') window.history.replaceState({}, '', '/');
    setView('dashboard');
  };

  if (view === 'loading') {
    return (
      <div className="ob-loading">
        <Logo size={44} />
      </div>
    );
  }
  if (view === 'onboarding') return <Onboarding onOpenDashboard={openDashboard} />;
  if (view === 'progress') return <ResumedProgress name={name} onOpenDashboard={openDashboard} />;
  return <Dashboard initialRoute={path === '/welcome' ? '/' : path} />;
}
