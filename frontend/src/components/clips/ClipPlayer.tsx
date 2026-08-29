import { Clip } from '@/types';
import { useAuthenticatedMediaUrl } from '@/hooks/useAuthenticatedMedia';

interface ClipPlayerProps {
  clip: Clip;
}

export function ClipPlayer({ clip }: ClipPlayerProps) {
  const videoUrl = useAuthenticatedMediaUrl(
    clip.video_file_path ? `/clips/${clip.id}/download` : null
  );

  return (
    <div className="mx-auto aspect-[9/16] w-full max-w-xs overflow-hidden rounded-2xl bg-black shadow-xl">
      {videoUrl ? (
        <video
          key={videoUrl}
          controls
          className="h-full w-full object-contain"
          src={videoUrl}
        >
          Your browser does not support the video tag.
        </video>
      ) : (
        <div className="flex h-full w-full items-center justify-center text-sm text-white/60">
          {clip.status === 'failed'
            ? 'Rendering failed — no video available.'
            : 'Video is still being generated…'}
        </div>
      )}
    </div>
  );
}
