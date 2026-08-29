import { useNavigate } from 'react-router-dom';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';

/** Prominent dashboard call-to-action that starts a new project. */
export function NewProjectCTA() {
  const navigate = useNavigate();

  return (
    <GlassCard className="flex flex-col items-start justify-between gap-4 bg-gradient-to-r from-purple-500/10 to-pink-500/10 sm:flex-row sm:items-center">
      <div>
        <h2 className="text-xl font-semibold text-gray-800">
          Turn a long video into shorts
        </h2>
        <p className="mt-1 text-sm text-gray-600">
          Upload a video or paste a URL and we&apos;ll find the best clips for
          you.
        </p>
      </div>
      <GradientButton
        onClick={() => navigate('/projects/new')}
        className="w-full shrink-0 sm:w-auto"
      >
        New Project
      </GradientButton>
    </GlassCard>
  );
}
