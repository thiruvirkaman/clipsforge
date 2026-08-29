import { motion } from 'framer-motion';
import { GlassCard } from '@/components/ui/GlassCard';
import { StatusBadge } from '@/components/projects/StatusBadge';
import { useProjectJobs } from '@/hooks/useProjects';
import { JobStatus, JobType, ProjectStatus } from '@/types';
import { cn } from '@/lib/utils';

interface ProcessingProgressProps {
  projectId: number;
  projectStatus: ProjectStatus;
}

const STEP_ORDER: { type: JobType; label: string }[] = [
  { type: 'transcription', label: 'Transcription' },
  { type: 'highlight_detection', label: 'Highlight detection' },
  { type: 'render', label: 'Rendering clips' },
];

function stepIndicatorClasses(status: JobStatus | 'pending'): string {
  switch (status) {
    case 'completed':
      return 'bg-emerald-500 border-emerald-500 text-white';
    case 'running':
      return 'bg-blue-500 border-blue-500 text-white';
    case 'failed':
      return 'bg-red-500 border-red-500 text-white';
    case 'queued':
    case 'pending':
    default:
      return 'bg-white border-gray-300 text-gray-400';
  }
}

export function ProcessingProgress({
  projectId,
  projectStatus,
}: ProcessingProgressProps) {
  const { data: jobs = [], isLoading } = useProjectJobs(projectId);

  return (
    <GlassCard>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-800">Processing</h3>
        <StatusBadge status={projectStatus} />
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-500">Loading job status…</p>
      ) : (
        <ol className="space-y-4">
          {STEP_ORDER.map((step, index) => {
            const job = jobs.find((j) => j.job_type === step.type);
            const status: JobStatus | 'pending' = job?.status ?? 'pending';

            return (
              <motion.li
                key={step.type}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className="flex items-start gap-3"
              >
                <span
                  className={cn(
                    'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 text-xs font-semibold',
                    stepIndicatorClasses(status)
                  )}
                >
                  {index + 1}
                </span>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <p className="font-medium text-gray-700">{step.label}</p>
                    {job && <StatusBadge status={job.status} />}
                  </div>
                  {job?.error_message && (
                    <p className="mt-1 text-sm text-red-500">
                      {job.error_message}
                    </p>
                  )}
                </div>
              </motion.li>
            );
          })}
        </ol>
      )}
    </GlassCard>
  );
}
