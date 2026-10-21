import { useEffect, useState, useMemo } from 'react';
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
import { api, type ApiJob, type ApiStateResponse } from '@/lib/api';
import { GoogleMapView } from './google-map-view';
import { MapOmnibox } from './map-omnibox';
import { MapPlaceCard } from './map-place-card';
import { MapExploreDrawer } from './map-explore-drawer';
import { MapStatusPill } from './map-status-pill';
import { CompareDialog } from './compare-dialog';
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

  // Transform backend jobs into rich Job format
  const allJobs: Job[] = useMemo(() => {
    return rawJobs.map(transformApiJob);
  }, [rawJobs]);

  // Dynamic sources
  const sources = useMemo(() => {
    return [...new Set(allJobs.map((j) => j.source))].filter(Boolean);
  }, [allJobs]);

  // Filtered dataset
  const filteredJobs = useMemo(() => {
    let result = filterJobs(allJobs, {
      search: ws.search,
      seniority: ws.seniority,
      location: ws.location,
      minimum: ws.minimum,
      sort: 'match',
      saved: ws.saved,
      shortlistOnly: ws.shortlistOnly,
    }).filter((j) => ws.source === 'all' || j.source === ws.source);

    if (selectedQuadrant !== 'all') {
      result = result.filter((j) => {
        const q = mapQuadrant(
          axisScore(j, ws.xAxis as MapAxis),
          axisScore(j, ws.yAxis as MapAxis),
          ws.threshold
        );
        return q === selectedQuadrant;
      });
    }

    return result;
  }, [allJobs, ws, selectedQuadrant]);

  const selectedJob = useMemo(() => {
    return allJobs.find((j) => j.id === selectedId) || null;
  }, [allJobs, selectedId]);

  const isNew = (job: Job) => newDays >= 0 && isNewSince(job, newDays);

  const resetFilters = () => {
    patch({
      search: '',
      seniority: 'all',
      location: 'all',
      minimum: 0,
      source: 'all',
      shortlistOnly: false,
    });
    setSelectedQuadrant('all');
  };

  const toggleSave = (id: string) => {
    patch({
      saved: ws.saved.includes(id) ? ws.saved.filter((x) => x !== id) : [...ws.saved, id],
    });
  };

  const toggleCompare = (id: string) => {
    setCompare((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id].slice(-2)
    );
  };

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
    setScanStatus('Starting live job radar scan...');
    const cleanup = api.createScanEventSource(
      (ev) => {
        if (ev.type === 'progress' || ev.type === 'scrape') {
          setScanStatus(ev.message || `Scanning ${ev.company || 'portals'}...`);
        } else if (ev.type === 'match' || ev.type === 'score') {
          setScanStatus(`Scoring ${ev.title || 'role'} (${ev.score || ''}/10)`);
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
        jobs={filteredJobs}
        selectedId={selectedId}
        hoveredId={hoveredId}
        onSelectJob={(id) => setSelectedId(id)}
        onHoverJob={(id) => setHoveredId(id)}
        isNew={isNew}
        xAxis={ws.xAxis as MapAxis}
        yAxis={ws.yAxis as MapAxis}
        threshold={ws.threshold}
        onAxesChange={(x, y) => patch({ xAxis: x, yAxis: y })}
        onThresholdChange={(t) => patch({ threshold: t })}
      />

      {/* 2. Floating Top-Left Omnibox (Search, Filter Chips, Scan, Settings) */}
      {!selectedJob && (
        <MapOmnibox
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
      {selectedJob && (
        <MapPlaceCard
          job={selectedJob}
          onClose={() => setSelectedId(null)}
          saved={ws.saved.includes(selectedJob.id)}
          onToggleSave={toggleSave}
          isComparing={compare.includes(selectedJob.id)}
          onToggleCompare={toggleCompare}
          onDiscard={handleDiscardJob}
        />
      )}

      {/* 4. Floating "Explore Results" Bottom Drawer */}
      <MapExploreDrawer
        jobs={filteredJobs}
        selectedId={selectedId}
        onSelectJob={(id) => setSelectedId(id)}
        onHoverJob={(id) => setHoveredId(id)}
        saved={ws.saved}
        onToggleSave={toggleSave}
        comparing={compare}
        onToggleCompare={toggleCompare}
        isNew={isNew}
        onResetFilters={resetFilters}
      />

      {/* 5. Floating Bottom-Left Radar Status & Compare Pill */}
      <MapStatusPill
        totalCount={filteredJobs.length}
        sweetCount={sweetCount}
        shortlistCount={ws.saved.length}
        compareCount={compare.length}
        onOpenCompare={() => setCompareOpen(true)}
        isScanning={scanning}
        scanStatus={scanStatus}
      />

      {/* 6. Modals (Compare, Profile, Settings) */}
      <CompareDialog
        jobs={compareJobs}
        open={compareOpen && compareJobs.length === 2}
        onOpenChange={setCompareOpen}
      />

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
