import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { JobStatus, ProjectStatus } from '@/types';

type BadgeStatus = ProjectStatus | JobStatus;

interface StatusConfig {
  label: string;
  className: string;
}

const STATUS_CONFIG: Record<BadgeStatus, StatusConfig> = {
  pending: {
    label: 'Pending',
    className: 'bg-gray-100 text-gray-600 border-gray-200',
  },
  transcribing: {
    label: 'Transcribing',
    className: 'bg-blue-100 text-blue-700 border-blue-200',
  },
  analyzing: {
    label: 'Analyzing',
    className: 'bg-purple-100 text-purple-700 border-purple-200',
  },
  ready: {
    label: 'Ready',
    className: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  },
  failed: {
    label: 'Failed',
    className: 'bg-red-100 text-red-700 border-red-200',
  },
  queued: {
    label: 'Queued',
    className: 'bg-gray-100 text-gray-600 border-gray-200',
  },
  running: {
    label: 'Running',
    className: 'bg-blue-100 text-blue-700 border-blue-200',
  },
  completed: {
    label: 'Completed',
    className: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  },
};

interface StatusBadgeProps {
  status: BadgeStatus;
  className?: string;
}

const PULSING_STATUSES: ReadonlySet<BadgeStatus> = new Set([
  'transcribing',
  'analyzing',
  'running',
  'pending',
  'queued',
]);

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium',
        config.className,
        className
      )}
    >
      {PULSING_STATUSES.has(status) && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
        </span>
      )}
      {config.label}
    </motion.span>
  );
}
