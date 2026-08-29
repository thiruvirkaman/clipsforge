import { useState } from 'react';
import { GradientButton } from '@/components/ui/GradientButton';
import { usePublishClip } from '@/hooks/usePublish';
import { Platform, ScheduledPost } from '@/types';

const PLATFORM_OPTIONS: { value: Platform; label: string }[] = [
  { value: 'tiktok', label: 'TikTok' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'youtube_shorts', label: 'YouTube Shorts' },
];

export interface PublishButtonProps {
  /** Id of the clip to publish. */
  clipId: number;
  /** Optional ISO datetime string; when set the post is scheduled rather than published immediately. */
  scheduledAt?: string;
  /** Called with the created/updated ScheduledPost after a successful publish request. */
  onPublished?: (post: ScheduledPost) => void;
  className?: string;
}

/**
 * Platform picker + publish trigger, meant to be dropped into the clip
 * detail page. Renders a small `<select>` of platforms alongside a
 * `GradientButton` that calls `POST /clips/{clipId}/publish` via
 * `usePublishClip()`.
 */
export function PublishButton({
  clipId,
  scheduledAt,
  onPublished,
  className,
}: PublishButtonProps) {
  const [platform, setPlatform] = useState<Platform>(
    PLATFORM_OPTIONS[0].value
  );
  const publishMutation = usePublishClip();

  const handlePublish = () => {
    publishMutation.mutate(
      { clipId, platform, scheduled_at: scheduledAt },
      {
        onSuccess: (post) => onPublished?.(post),
      }
    );
  };

  return (
    <div className={className}>
      <div className="flex items-center gap-3">
        <select
          value={platform}
          onChange={(event) => setPlatform(event.target.value as Platform)}
          disabled={publishMutation.isPending}
          className="rounded-full border-2 border-gray-200 px-4 py-3 text-sm font-medium text-gray-700 outline-none focus:border-purple-500"
        >
          {PLATFORM_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <GradientButton
          type="button"
          disabled={publishMutation.isPending}
          onClick={handlePublish}
        >
          {publishMutation.isPending
            ? 'Publishing...'
            : scheduledAt
              ? 'Schedule'
              : 'Publish'}
        </GradientButton>
      </div>

      {publishMutation.isError && (
        <p className="mt-2 text-sm text-red-500">
          Failed to publish clip. Please try again.
        </p>
      )}
      {publishMutation.isSuccess && (
        <p className="mt-2 text-sm text-emerald-600">
          Publish request submitted.
        </p>
      )}
    </div>
  );
}
