import { AnimatedList } from '@/components/ui/AnimatedList';
import { GlassCard } from '@/components/ui/GlassCard';
import { Platform, PostStatus, ScheduledPost } from '@/types';

const PLATFORM_LABELS: Record<Platform, string> = {
  tiktok: 'TikTok',
  instagram: 'Instagram',
  youtube_shorts: 'YouTube Shorts',
};

const STATUS_CLASSES: Record<PostStatus, string> = {
  scheduled: 'bg-blue-100 text-blue-700 border-blue-200',
  publishing: 'bg-purple-100 text-purple-700 border-purple-200',
  published: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  failed: 'bg-red-100 text-red-700 border-red-200',
};

const STATUS_LABELS: Record<PostStatus, string> = {
  scheduled: 'Scheduled',
  publishing: 'Publishing',
  published: 'Published',
  failed: 'Failed',
};

function formatDateTime(isoDate: string | null): string {
  if (isoDate === null) return 'Not scheduled';
  return new Date(isoDate).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

interface PostStatusTableProps {
  posts: ScheduledPost[];
  className?: string;
}

export function PostStatusTable({ posts, className }: PostStatusTableProps) {
  if (posts.length === 0) {
    return (
      <GlassCard className={className}>
        <p className="text-center text-sm text-gray-500">
          No scheduled or published posts yet.
        </p>
      </GlassCard>
    );
  }

  return (
    <AnimatedList className={className}>
      {posts.map((post) => (
        <GlassCard key={post.id} className="mb-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold text-gray-800">
                {PLATFORM_LABELS[post.platform]}
              </p>
              <p className="text-sm text-gray-500">
                Clip #{post.clip_id} &middot;{' '}
                {formatDateTime(post.scheduled_at)}
              </p>
            </div>

            <span
              className={`inline-flex w-fit items-center rounded-full border px-3 py-1 text-xs font-medium ${STATUS_CLASSES[post.status]}`}
            >
              {STATUS_LABELS[post.status]}
            </span>
          </div>

          {post.status === 'published' && post.published_url && (
            <a
              href={post.published_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 block truncate text-sm font-medium text-purple-600 hover:underline"
            >
              {post.published_url}
            </a>
          )}

          {post.status === 'failed' && post.error_message && (
            <p className="mt-3 text-sm text-red-500">{post.error_message}</p>
          )}
        </GlassCard>
      ))}
    </AnimatedList>
  );
}
