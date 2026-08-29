import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';
import { Platform, PublishConnection, ScheduledPost } from '@/types';

/** Post statuses that indicate the publish is still in flight. */
const IN_FLIGHT_STATUSES: ReadonlySet<ScheduledPost['status']> = new Set([
  'scheduled',
  'publishing',
]);

const SCHEDULED_POSTS_POLL_MS = 5000;

interface AuthorizeUrlResponse {
  authorize_url: string;
}

/** Lists the caller's connected publishing platforms. */
export function useConnections() {
  return useQuery({
    queryKey: ['publish', 'connections'],
    queryFn: async (): Promise<PublishConnection[]> => {
      const { data } = await api.get<PublishConnection[]>(
        '/publish/connections'
      );
      return data;
    },
  });
}

/**
 * Kicks off the OAuth connect flow for a platform. On success the browser
 * is redirected to the platform's `authorize_url`, so callers typically
 * don't need to handle the resolved value themselves.
 */
export function useConnectPlatform() {
  return useMutation({
    mutationFn: async (platform: Platform): Promise<AuthorizeUrlResponse> => {
      const { data } = await api.post<AuthorizeUrlResponse>(
        `/publish/connections/${platform}`
      );
      return data;
    },
    onSuccess: (data) => {
      window.location.href = data.authorize_url;
    },
  });
}

/** Disconnects a connected platform account by connection id. */
export function useDisconnectPlatform() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (connectionId: number): Promise<void> => {
      await api.delete(`/publish/connections/${connectionId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['publish', 'connections'] });
    },
  });
}

/**
 * Lists scheduled/published posts. Polls periodically while any post is
 * still scheduled or publishing so status updates without a manual refresh.
 */
export function useScheduledPosts() {
  return useQuery({
    queryKey: ['publish', 'posts'],
    queryFn: async (): Promise<ScheduledPost[]> => {
      const { data } = await api.get<ScheduledPost[]>('/publish/posts');
      return data;
    },
    refetchInterval: (query) => {
      const posts = query.state.data ?? [];
      const hasInFlightPost = posts.some((post) =>
        IN_FLIGHT_STATUSES.has(post.status)
      );
      return hasInFlightPost ? SCHEDULED_POSTS_POLL_MS : false;
    },
  });
}

export interface PublishClipInput {
  clipId: number;
  platform: Platform;
  scheduled_at?: string;
}

/** Publishes (or schedules) a clip to a platform. */
export function usePublishClip() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      clipId,
      platform,
      scheduled_at,
    }: PublishClipInput): Promise<ScheduledPost> => {
      const { data } = await api.post<ScheduledPost>(
        `/clips/${clipId}/publish`,
        { platform, scheduled_at }
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['publish', 'posts'] });
    },
  });
}
