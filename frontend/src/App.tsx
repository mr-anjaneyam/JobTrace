import { Dashboard } from '@/components/jobtrace/dashboard';

export function App() {
  const currentPath = typeof window !== 'undefined' ? window.location.pathname : '/';
  return <Dashboard initialRoute={currentPath} />;
}
