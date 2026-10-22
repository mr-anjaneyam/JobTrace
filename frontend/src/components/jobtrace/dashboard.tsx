import { useEffect, useState, useMemo, useCallback, useDeferredValue, useRef, lazy, Suspense } from 'react';
import {
  filterJobs,
  mapQuadrant,
  axisScore,
  isNewSince,
  transformApiJob,
  type Job,
  type MapAxis,
} from '@/lib/jobs';
import { useWorkspace } from '@/hooks/use-workspace';
import { usePresence } from '@/hooks/use-presence';
import { api, type ApiJob, type ApiStateResponse } from '@/lib/api';
import { GoogleMapView } from './google-map-view';
import { MapOmnibox } from './map-omnibox';
import { MapPlaceCard } from './map-place-card';
import { MapExploreDrawer } from './map-explore-drawer';
import { MapStatusPill } from './map-status-pill';
const CompareDialog = lazy(() => import('./compare-dialog').then((m) => ({ default: m.CompareDialog })));
import { UserProfileDialog } from './userprofile-dialog';
import { SettingsDialog } from './settings-dialog';

export function Dashboard({
  initialRoute = '/',
}: {
  initialRoute?: string;
}) {
  const { state: ws, patch, newDays } = useWorkspace();
  const [rawJobs, setRawJobs] = useState<ApiJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanStatus, setScanStatus] = useState<string | null>(null);

  // Selected & Hovered Job IDs
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // Quadrant Filter
  const [selectedQuadrant, setSelectedQuadrant] = useState<'all' | 'sweet' | 'stretch' | 'safety'>('all');

  // Job Compare State
  const [compare, setCompare] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);

  // Dialog Modals
  const [profileOpen, setProfileOpen] = useState(initialRoute === '/userprofile');
  const [settingsOpen, setSettingsOpen] = useState(initialRoute === '/settings');

  // Route Synchronization
  const navigateTo = (path: string) => {
    if (path === '/userprofile') {
      setProfileOpen(true);
      setSettingsOpen(false);
      window.history.pushState({}, '', '/userprofile');
    } else if (path === '/settings') {
      setSettingsOpen(true);
      setProfileOpen(false);
      window.history.pushState({}, '', '/settings');
    } else {
      setProfileOpen(false);
      setSettingsOpen(false);
      window.history.pushState({}, '', '/');
    }
  };

  useEffect(() => {
    const handlePopState = () => {
      const p = window.location.pathname;
      setProfileOpen(p === '/userprofile');
      setSettingsOpen(p === '/settings');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Fetch live state from backend
  const loadState = async () => {
    try {
      const res: ApiStateResponse = await api.getState();
      setRawJobs(res.jobs || []);
      setScanning(res.scanning || false);
    } catch (e) {
      console.error('Failed to load state from JobTrace API:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadState();
  }, []);

  // Full-text (FTS5) search across titles, companies, locations and descriptions
  const [ftsIds, setFtsIds] = useState<Set<string> | null>(null);
  useEffect(() => {
    const q = ws.search.trim();
    if (!q) {
      setFtsIds(null);
      return;
    }
    const ctrl = new AbortController();
    setFtsIds(null);
    api
      .search(q, ctrl.signal)
      .then((ids) => setFtsIds(ids ? new Set(ids) : null))
      .catch(() => {
        if (!ctrl.signal.aborted) setFtsIds(null);
      });
    return () => ctrl.abort();
  }, [ws.search]);

  // Transform backend jobs into rich Job format
  const allJobs: Job[] = useMemo(() => {
    return rawJobs.map(transformApiJob);
  }, [rawJobs]);

  // Dynamic sources
  const sources = useMemo(() => {
    return [...new Set(allJobs.map((j) => j.source))].filter(Boolean);
  }, [allJobs]);

  // Text/attribute filters; independent of the map axes and threshold so dragging those stays cheap
  const baseFiltered = useMemo(() => {
    // FTS ids cover full descriptions; fall back to client-side title/company match until they arrive
    const useFts = ws.search.trim() !== '' && ftsIds !== null;
    let result = filterJobs(allJobs, {
      search: useFts ? '' : ws.search,
      seniority: ws.seniority,
      location: ws.location,
      minimum: ws.minimum,
      sort: 'match',
      saved: ws.saved,
      shortlistOnly: ws.shortlistOnly,
    }).filter((j) => ws.source === 'all' || j.source === ws.source);

    if (useFts && ftsIds) {
      result = result.filter((j) => ftsIds.has(j.id));
    }
    return result;
  }, [allJobs, ws.search, ws.seniority, ws.location, ws.minimum, ws.saved, ws.shortlistOnly, ws.source, ftsIds]);

  const filteredJobs = useMemo(() => {
    if (selectedQuadrant === 'all') return baseFiltered;
    return baseFiltered.filter((j) => {
      const q = mapQuadrant(
        axisScore(j, ws.xAxis as MapAxis),
        axisScore(j, ws.yAxis as MapAxis),
        ws.threshold
      );
      return q === selectedQuadrant;
    });
  }, [baseFiltered, selectedQuadrant, ws.xAxis, ws.yAxis, ws.threshold]);

  // Defer heavy canvas & drawer updates so interactive filters/views respond immediately
  const deferredFilteredJobs = useDeferredValue(filteredJobs);

  const selectedJob = useMemo(() => {
    return allJobs.find((j) => j.id === selectedId) || null;
  }, [allJobs, selectedId]);

  const isNew = useCallback((job: Job) => newDays >= 0 && isNewSince(job, newDays), [newDays]);

  const placeCard = usePresence(selectedJob, 260);
  const omnibox = usePresence(selectedJob ? null : true, 200);

  const resetFilters = useCallback(() => {
    patch({
      search: '',
      seniority: 'all',
      location: 'all',
      minimum: 0,
      source: 'all',
      shortlistOnly: false,
    });
    setSelectedQuadrant('all');
  }, [patch]);

  const toggleSave = useCallback((id: string) => {
    patch({
      saved: ws.saved.includes(id) ? ws.saved.filter((x) => x !== id) : [...ws.saved, id],
    });
  }, [patch, ws.saved]);

  const toggleCompare = useCallback((id: string) => {
    setCompare((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id].slice(-2)
    );
  }, []);

  const handleSelectJob = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const handleHoverJob = useCallback((id: string | null) => {
    setHoveredId(id);
  }, []);

  const handleAxesChange = useCallback(
    (x: MapAxis, y: MapAxis) => patch({ xAxis: x, yAxis: y }),
    [patch]
  );

  const handleThresholdChange = useCallback((t: number) => patch({ threshold: t }), [patch]);

  const lastStatusAt = useRef(0);
  const throttledStatus = useCallback((text: string) => {
    const now = performance.now();
    if (now - lastStatusAt.current < 250) return;
    lastStatusAt.current = now;
    setScanStatus(text);
  }, []);

  const handleDiscardJob = async (id: string) => {
    try {
      await api.discardJob(id);
      setRawJobs((prev) => prev.filter((j) => j.id !== id));
      if (selectedId === id) setSelectedId(null);
    } catch (err) {
      console.error('Failed to discard job:', err);
    }
  };

  const handlePurgeClosed = async () => {
    try {
      const res = await api.discardClosedJobs();
      if (res.total_closed > 0) {
        await loadState();
      }
      return res;
    } catch (err) {
      console.error('Failed to purge closed jobs:', err);
    }
  };

  const compareJobs = compare
    .map((id) => allJobs.find((j) => j.id === id))
    .filter((j): j is NonNullable<typeof j> => Boolean(j));

  // Trigger live scan with SSE updates
  const handleTriggerScan = () => {
    if (scanning) return;
    setScanning(true);
    setScanStatus('Starting live JobTrace scan...');
    const cleanup = api.createScanEventSource(
      (ev) => {
        if (ev.type === 'fetch') {
          throttledStatus(`Fetched ${ev.company || 'portal'} (${ev.count ?? 0} open)`);
        } else if (ev.type === 'scoring') {
          throttledStatus(`Scoring ${ev.count ?? 0} new roles...`);
        } else if (ev.type === 'looking' || ev.type === 'scored') {
          throttledStatus(`Scoring ${ev.company || ''} ${ev.title || 'role'}`.trim());
        } else if (ev.type === 'throttled' || ev.type === 'error') {
          setScanStatus(ev.message || 'Scan paused');
        }
      },
      (err) => {
        console.error('Scan error:', err);
      },
      () => {
        setScanning(false);
        setScanStatus(null);
        loadState();
      }
    );
  };

  // Count active filters
  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (ws.search) count++;
    if (ws.seniority !== 'all') count++;
    if (ws.location !== 'all') count++;
    if (ws.source !== 'all') count++;
    if (ws.minimum > 0) count++;
    if (ws.shortlistOnly) count++;
    if (selectedQuadrant !== 'all') count++;
    return count;
  }, [ws, selectedQuadrant]);

  // Quadrant counts
  const sweetCount = useMemo(() => {
    return allJobs.filter(
      (j) =>
        mapQuadrant(
          axisScore(j, ws.xAxis as MapAxis),
          axisScore(j, ws.yAxis as MapAxis),
          ws.threshold
        ) === 'sweet'
    ).length;
  }, [allJobs, ws.xAxis, ws.yAxis, ws.threshold]);

  return (
    <div className="gmap-root-container">
      {/* 1. Full-Screen Interactive Opportunity Map Canvas */}
      <GoogleMapView
        jobs={deferredFilteredJobs}
        selectedId={selectedId}
        hoveredId={hoveredId}
        onSelectJob={handleSelectJob}
        isNew={isNew}
        xAxis={ws.xAxis as MapAxis}
        yAxis={ws.yAxis as MapAxis}
        threshold={ws.threshold}
        onAxesChange={handleAxesChange}
        onThresholdChange={handleThresholdChange}
      />

      {/* 2. Floating Top-Left Omnibox (Search, Filter Chips, Scan, Settings) */}
      {omnibox.item && (
        <MapOmnibox
          state={omnibox.state}
          searchQuery={ws.search}
          onSearchChange={(q) => patch({ search: q })}
          shortlistOnly={ws.shortlistOnly}
          onToggleShortlist={() => patch({ shortlistOnly: !ws.shortlistOnly })}
          shortlistCount={ws.saved.length}
          seniority={ws.seniority}
          onSeniorityChange={(s) => patch({ seniority: s })}
          location={ws.location}
          onLocationChange={(loc) => patch({ location: loc })}
          source={ws.source}
          onSourceChange={(src) => patch({ source: src })}
          sources={sources}
          minimumScore={ws.minimum}
          onMinimumScoreChange={(score) => patch({ minimum: score })}
          selectedQuadrant={selectedQuadrant}
          onQuadrantChange={(q) => setSelectedQuadrant(q)}
          isScanning={scanning}
          scanStatus={scanStatus}
          onTriggerScan={handleTriggerScan}
          onOpenProfile={() => navigateTo('/userprofile')}
          onOpenSettings={() => navigateTo('/settings')}
          onResetFilters={resetFilters}
          activeFilterCount={activeFilterCount}
          onPurgeClosed={handlePurgeClosed}
        />
      )}

      {/* 3. Floating Place Details Card (Slides in when any job is clicked) */}
      {placeCard.item && (
        <MapPlaceCard
          state={placeCard.state}
          job={placeCard.item}
          onClose={() => setSelectedId(null)}
          saved={ws.saved.includes(placeCard.item.id)}
          onToggleSave={toggleSave}
          isComparing={compare.includes(placeCard.item.id)}
          onToggleCompare={toggleCompare}
          onDiscard={handleDiscardJob}
        />
      )}

      {/* 4. Floating "Explore Results" Bottom Drawer */}
      <MapExploreDrawer
        jobs={deferredFilteredJobs}
        selectedId={selectedId}
        onSelectJob={handleSelectJob}
        onHoverJob={handleHoverJob}
        saved={ws.saved}
        onToggleSave={toggleSave}
        comparing={compare}
        onToggleCompare={toggleCompare}
        isNew={isNew}
        onResetFilters={resetFilters}
      />

      {/* 5. Floating Bottom-Left Radar Status & Compare Pill */}
      <MapStatusPill
        totalCount={deferredFilteredJobs.length}
        sweetCount={sweetCount}
        shortlistCount={ws.saved.length}
        compareCount={compare.length}
        onOpenCompare={() => setCompareOpen(true)}
        isScanning={scanning}
        scanStatus={scanStatus}
      />

      {/* 6. Modals (Compare, Profile, Settings) */}
      {compareOpen && compareJobs.length === 2 && (
        <Suspense fallback={null}>
          <CompareDialog jobs={compareJobs} open onOpenChange={setCompareOpen} />
        </Suspense>
      )}

      <UserProfileDialog
        open={profileOpen}
        onOpenChange={(open) => {
          setProfileOpen(open);
          if (!open && window.location.pathname === '/userprofile') {
            window.history.pushState({}, '', '/');
          }
        }}
        onProfileUpdated={loadState}
      />

      <SettingsDialog
        open={settingsOpen}
        onOpenChange={(open) => {
          setSettingsOpen(open);
          if (!open && window.location.pathname === '/settings') {
            window.history.pushState({}, '', '/');
          }
        }}
        onSettingsUpdated={loadState}
      />
    </div>
  );
}
