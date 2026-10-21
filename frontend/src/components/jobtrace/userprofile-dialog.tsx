import { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api, type ApiProfile } from '@/lib/api';
import { User, Upload, Check, AlertCircle, FileText, Sparkles, MapPin, Briefcase, GraduationCap } from 'lucide-react';

export function UserProfileDialog({
  open,
  onOpenChange,
  onProfileUpdated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onProfileUpdated?: () => void;
}) {
  const [profile, setProfile] = useState<ApiProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      loadProfile();
    }
  }, [open]);

  const loadProfile = async () => {
    setLoading(true);
    setStatusMsg(null);
    try {
      const data = await api.getProfile();
      setProfile(data);
    } catch (e: any) {
      setStatusMsg({ type: 'error', text: e.message || 'Failed to load profile' });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!profile) return;
    setSaving(true);
    setStatusMsg(null);
    try {
      await api.updateProfile(profile);
      setStatusMsg({ type: 'success', text: 'Candidate profile saved successfully!' });
      if (onProfileUpdated) onProfileUpdated();
    } catch (e: any) {
      setStatusMsg({ type: 'error', text: e.message || 'Failed to save profile' });
    } finally {
      setSaving(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setStatusMsg(null);
    try {
      const res = await api.uploadResume(file);
      if (res.ok && res.profile) {
        setProfile(res.profile);
        setStatusMsg({ type: 'success', text: `Resume '${res.filename}' parsed and profile refreshed!` });
        if (onProfileUpdated) onProfileUpdated();
      } else {
        setStatusMsg({ type: 'error', text: res.error || 'Failed to parse resume' });
      }
    } catch (e: any) {
      setStatusMsg({ type: 'error', text: e.message || 'Upload error' });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Safe skills array extractor
  const skillsList: string[] = (() => {
    if (!profile || !profile.skills) return [];
    if (Array.isArray(profile.skills)) return profile.skills;
    if (typeof profile.skills === 'string') {
      return (profile.skills as string)
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
    }
    return [];
  })();

  // Safe target locations string
  const targetLocationsValue: string = (() => {
    if (!profile || !profile.target_locations) return '';
    if (Array.isArray(profile.target_locations)) return profile.target_locations.join(', ');
    if (typeof profile.target_locations === 'string') return profile.target_locations;
    return '';
  })();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[88vh] overflow-y-auto p-6">
        <DialogTitle className="sr-only">Candidate Profile</DialogTitle>
        <div className="flex items-center justify-between pb-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-full bg-secondary flex items-center justify-center text-primary font-display font-semibold">
              <User size={20} />
            </div>
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Candidate Profile</h2>
              <p className="text-xs text-muted-foreground">Manage your background, resume, and seniority gating.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".pdf,.txt,.docx,.md"
              className="hidden"
            />
            <Button
              variant="outline"
              size="sm"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload size={13} />
              {uploading ? 'Parsing...' : 'Upload Resume'}
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saving || loading}>
              {saving ? 'Saving...' : 'Save Profile'}
            </Button>
          </div>
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
          <div className="py-12 text-center text-muted-foreground text-sm flex items-center justify-center gap-2">
            <Sparkles size={16} className="animate-spin text-primary" />
            Loading candidate profile...
          </div>
        ) : profile ? (
          <div className="space-y-5 pt-2">
            {/* Identity & Headline */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Full Name</label>
                <Input
                  value={profile.name || ''}
                  onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                  placeholder="e.g. Alex Morgan"
                  className="h-9 text-xs"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Professional Headline</label>
                <Input
                  value={profile.headline || ''}
                  onChange={(e) => setProfile({ ...profile, headline: e.target.value })}
                  placeholder="e.g. Frontend Engineer · React & TS"
                  className="h-9 text-xs"
                />
              </div>
            </div>

            {/* Seniority & Locations */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Assigned Seniority</label>
                <select
                  value={(profile.seniority || 'junior').toLowerCase()}
                  onChange={(e) => setProfile({ ...profile, seniority: e.target.value })}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="junior">Junior (0 - 2 years)</option>
                  <option value="mid">Mid-level (2 - 5 years)</option>
                  <option value="senior">Senior (5+ years)</option>
                </select>
                <p className="text-[11px] text-muted-foreground mt-1">
                  {profile.seniority_reason || 'Used to accurately evaluate senior scope requirements.'}
                </p>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Target Locations (comma-separated)</label>
                <Input
                  value={targetLocationsValue}
                  onChange={(e) =>
                    setProfile({
                      ...profile,
                      target_locations: e.target.value
                        .split(',')
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                  placeholder="Remote, London, San Francisco, Bangalore"
                  className="h-9 text-xs"
                />
              </div>
            </div>

            {/* Skills */}
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Extracted Skills ({skillsList.length})</label>
              <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto p-2 rounded-md border border-border bg-muted/30">
                {skillsList.length > 0 ? (
                  skillsList.map((skill) => (
                    <span
                      key={skill}
                      className="px-2 py-0.5 rounded text-[11px] bg-secondary text-primary font-medium"
                    >
                      {skill}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-muted-foreground">Upload a resume to auto-extract core skills.</span>
                )}
              </div>
            </div>

            {/* Experience highlights */}
            {profile.experience && profile.experience.length > 0 && (
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Experience History</label>
                <div className="space-y-2.5 max-h-56 overflow-y-auto pr-1">
                  {profile.experience.map((exp: any, i) => {
                    const company = exp.company || exp.org || 'Company';
                    const title = exp.title || exp.role || 'Role';
                    const duration = exp.duration || exp.years || '';

                    let highlightsList: string[] = [];
                    if (Array.isArray(exp.highlights)) {
                      highlightsList = exp.highlights;
                    } else if (typeof exp.highlights === 'string' && exp.highlights.trim()) {
                      highlightsList = exp.highlights
                        .split(/[•\n]/)
                        .map((s: string) => s.trim())
                        .filter(Boolean);
                    }

                    return (
                      <div key={i} className="p-3 rounded-md border border-border bg-card text-xs">
                        <div className="flex items-center justify-between font-medium">
                          <span className="text-foreground font-semibold">{title}</span>
                          <span className="text-muted-foreground font-normal">{duration}</span>
                        </div>
                        <div className="text-primary font-medium mt-0.5">{company}</div>
                        {highlightsList.length > 0 && (
                          <ul className="mt-1.5 list-disc list-inside space-y-1 text-muted-foreground text-[11px] leading-relaxed">
                            {highlightsList.slice(0, 3).map((h, j) => (
                              <li key={j}>{h}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Education History if present */}
            {profile.education && profile.education.length > 0 && (
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1.5 block">Education</label>
                <div className="space-y-2">
                  {profile.education.map((edu: any, i) => (
                    <div key={i} className="p-2.5 rounded-md border border-border bg-muted/20 text-xs flex items-center justify-between">
                      <div>
                        <div className="font-medium text-foreground">{edu.degree}</div>
                        <div className="text-muted-foreground text-[11px]">{edu.institution}</div>
                      </div>
                      {edu.year && <span className="text-muted-foreground text-[11px]">{edu.year}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-muted-foreground">
            No profile information found. Upload a resume to generate your candidate profile.
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
