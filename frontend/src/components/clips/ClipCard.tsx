import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { GlassCard } from '@/components/ui/GlassCard';
import { cn } from '@/lib/utils';
import { useAuthenticatedMediaUrl } from '@/hooks/useAuthenticatedMedia';
import { Clip, ClipStatus } from '@/types';

interface ClipCardProps {
  clip: Clip;
}

interface StatusConfig {
  label: string;
  className: string;
  pulsing: boolean;
}

const STATUS_CONFIG: Record<ClipStatus, StatusConfig> = {
  queued: {
    label: 'Queued',
    className: 'bg-gray-100 text-gray-600 border-gray-200',
    pulsing: true,
  },
  rendering: {
    label: 'Rendering',
    className: 'bg-blue-100 text-blue-700 border-blue-200',
    pulsing: true,
  },
  ready: {
    label: 'Ready',
    className: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    pulsing: false,
  },
  failed: {
    label: 'Failed',
    className: 'bg-red-100 text-red-700 border-red-200',
    pulsing: false,
  },
};

function formatDuration(startTime: number, endTime: number): string {
  const seconds = Math.max(0, Math.round(endTime - startTime));
  return `${seconds}s`;
}

export function ClipCard({ clip }: ClipCardProps) {
  const navigate = useNavigate();
  const statusConfig = STATUS_CONFIG[clip.status];
  const thumbnailUrl = useAuthenticatedMediaUrl(
    clip.thumbnail_path ? `/clips/${clip.id}/thumbnail` : null
  );

  return (
    <div
      className="cursor-pointer"
      onClick={() => navigate(`/clips/${clip.id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={(event: React.KeyboardEvent<HTMLDivElement>) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          navigate(`/clips/${clip.id}`);
        }
      }}
    >
      <GlassCard className="overflow-hidden p-0 transition-shadow hover:shadow-2xl">
        <div className="relative aspect-[9/16] w-full overflow-hidden bg-gray-900/10">
          {thumbnailUrl ? (
            <img
              src={thumbnailUrl}
              alt={clip.title}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-sm text-gray-400">
              No preview yet
            </div>
          )}

          <motion.span
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className={cn(
              'absolute right-2 top-2 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium',
              statusConfig.className
            )}
          >
            {statusConfig.pulsing && (
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
              </span>
            )}
            {statusConfig.label}
          </motion.span>
        </div>

        <div className="p-4">
          <h3 className="line-clamp-2 text-sm font-semibold text-gray-800">
            {clip.title}
          </h3>
          <p className="mt-1 text-xs text-gray-500">
            {formatDuration(clip.start_time, clip.end_time)}
          </p>
        </div>
      </GlassCard>
    </div>
  );
}
