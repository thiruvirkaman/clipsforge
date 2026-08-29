import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { ClipPlayer } from '@/components/clips/ClipPlayer';
import { TranscriptPanel } from '@/components/clips/TranscriptPanel';
import { TrimControls } from '@/components/clips/TrimControls';
import { useClip, useDeleteClip } from '@/hooks/useClips';
import { useAuthenticatedMediaUrl } from '@/hooks/useAuthenticatedMedia';

export default function ClipDetailPage() {
  const params = useParams<{ id: string }>();
  const clipId = params.id ? Number(params.id) : undefined;
  const navigate = useNavigate();

  const { data: clip, isLoading, isError } = useClip(clipId);
  const deleteClip = useDeleteClip(clipId);
  const downloadUrl = useAuthenticatedMediaUrl(
    clip?.video_file_path ? `/clips/${clip.id}/download` : null
  );

  const handleDelete = () => {
    if (!clip) return;
    const confirmed = window.confirm(
      'Delete this clip? This action cannot be undone.'
    );
    if (!confirmed) return;
    deleteClip.mutate(undefined, {
      onSuccess: () => navigate(`/projects/${clip.project_id}`),
    });
  };

  if (isLoading) {
    return (
      <PageWrapper>
        <div className="flex min-h-screen items-center justify-center">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            className="h-10 w-10 rounded-full border-4 border-purple-200 border-t-purple-500"
          />
        </div>
      </PageWrapper>
    );
  }

  if (isError || !clip) {
    return (
      <PageWrapper>
        <div className="flex min-h-screen items-center justify-center px-4">
          <GlassCard className="max-w-md text-center">
            <p className="text-gray-600">
              This clip could not be found or failed to load.
            </p>
          </GlassCard>
        </div>
      </PageWrapper>
    );
  }

  return (
    <PageWrapper>
      <div className="mx-auto max-w-5xl px-4 py-10">
        <button
          type="button"
          onClick={() => navigate(`/projects/${clip.project_id}`)}
          className="mb-6 text-sm font-medium text-purple-600 hover:text-purple-700"
        >
          &larr; Back to project
        </button>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,320px)_1fr]">
          <GlassCard>
            <ClipPlayer clip={clip} />
            {downloadUrl && (
              <a
                href={downloadUrl}
                download={`${clip.title || 'clip'}.mp4`}
                className="mt-4 block w-full rounded-full border-2 border-purple-200 px-6 py-3 text-center text-sm font-semibold text-purple-600 transition-colors hover:border-purple-400 hover:bg-purple-50"
              >
                Download
              </a>
            )}
          </GlassCard>

          <div className="flex flex-col gap-6">
            <GlassCard>
              <h1 className="text-xl font-bold text-gray-800">
                {clip.title}
              </h1>
              <p className="mt-1 text-sm text-gray-500">
                {clip.start_time.toFixed(1)}s &ndash; {clip.end_time.toFixed(1)}s
                {' · '}
                {clip.aspect_ratio}
              </p>
            </GlassCard>

            <TranscriptPanel clip={clip} />

            <GlassCard>
              <TrimControls clip={clip} />
            </GlassCard>

            <GlassCard>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
                Danger zone
              </h2>
              <GradientButton
                type="button"
                className="!bg-gradient-to-r !from-red-500 !to-rose-500"
                disabled={deleteClip.isPending}
                onClick={handleDelete}
              >
                {deleteClip.isPending ? 'Deleting…' : 'Delete'}
              </GradientButton>
              {deleteClip.isError && (
                <p className="mt-2 text-sm text-red-500">
                  Failed to delete this clip. Please try again.
                </p>
              )}
            </GlassCard>
          </div>
        </div>
      </div>
    </PageWrapper>
  );
}
