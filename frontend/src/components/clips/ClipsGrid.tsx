import { motion } from 'framer-motion';
import { AnimatedList } from '@/components/ui/AnimatedList';
import { ClipCard } from '@/components/clips/ClipCard';
import { useClips } from '@/hooks/useClips';

interface ClipsGridProps {
  projectId: number;
}

const ACTIVE_STATUSES = new Set(['queued', 'rendering']);

export function ClipsGrid({ projectId }: ClipsGridProps) {
  const { data: clips, isLoading, isError } = useClips(projectId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          className="h-8 w-8 rounded-full border-4 border-purple-200 border-t-purple-500"
        />
      </div>
    );
  }

  if (isError) {
    return (
      <p className="py-16 text-center text-sm text-red-500">
        Failed to load clips. Please try again.
      </p>
    );
  }

  if (!clips || clips.length === 0) {
    return (
      <p className="py-16 text-center text-sm text-gray-500">
        No clips yet. Clips will appear here once generation starts.
      </p>
    );
  }

  const hasActiveClip = clips.some((clip) => ACTIVE_STATUSES.has(clip.status));

  return (
    <div>
      {hasActiveClip && (
        <p className="mb-4 text-sm text-gray-500">
          Generating clips&hellip; this list updates automatically.
        </p>
      )}
      <AnimatedList className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {clips.map((clip) => (
          <ClipCard key={clip.id} clip={clip} />
        ))}
      </AnimatedList>
    </div>
  );
}
