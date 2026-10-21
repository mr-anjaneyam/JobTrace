import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { type Job } from '@/lib/jobs';
import { JobDetail } from './job-detail';

export function JobDetailDialog({
  job,
  open,
  onOpenChange,
  saved,
  onSave,
}: {
  job: Job | undefined;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  saved: boolean;
  onSave: () => void;
}) {
  if (!job) return null;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="role-dialog">
        <DialogTitle className="sr-only">
          {job.company} — {job.title}
        </DialogTitle>
        <JobDetail job={job} saved={saved} onSave={onSave} />
      </DialogContent>
    </Dialog>
  );
}
