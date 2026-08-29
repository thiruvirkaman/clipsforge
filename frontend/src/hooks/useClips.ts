import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';
import { Clip } from '@/types';

/** Clip statuses that indicate rendering is still in progress. */
const PROCESSING_STATUSES: ReadonlySet<Clip['status']> = new Set([
  'queued',
  'rendering',
]);

const CLIPS_LIST_POLL_MS = 4000;
const CLIP_DETAIL_POLL_MS = 3000;

/**
 * Lists a project's clips. Polls periodically while any clip in the
 * last-fetched page is still queued/rendering, so cards flip to
 * "ready"/"failed" without a manual refresh.
 */
export function useClips(projectId: number | undefined) {
  return useQuery({
    queryKey: ['projects', projectId, 'clips'],
    queryFn: async (): Promise<Clip[]> => {
      const { data } = await api.get<Clip[]>(`/projects/${projectId}/clips`);
      return data;
    },
    enabled: projectId !== undefined,
    refetchInterval: (query) => {
      const clips = query.state.data ?? [];
      const hasActiveClip = clips.some((clip) =>
        PROCESSING_STATUSES.has(clip.status)
      );
      return hasActiveClip ? CLIPS_LIST_POLL_MS : false;
    },
  });
}

/**
 * Fetches a single clip. Polls while it hasn't reached a terminal status
 * (`ready` or `failed`) so the detail page reflects rendering progress live.
 */
export function useClip(id: number | undefined) {
  return useQuery({
    queryKey: ['clips', id],
    queryFn: async (): Promise<Clip> => {
      const { data } = await api.get<Clip>(`/clips/${id}`);
      return data;
    },
    enabled: id !== undefined,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status) return false;
      return status !== 'ready' && status !== 'failed'
        ? CLIP_DETAIL_POLL_MS
        : false;
    },
  });
}

export interface RegenerateClipInput {
  start_time?: number;
  end_time?: number;
}

/** Requests a clip re-render, optionally with adjusted trim points. */
export function useRegenerateClip(id: number | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input?: RegenerateClipInput): Promise<Clip> => {
      const { data } = await api.post<Clip>(`/clips/${id}/regenerate`, input);
      return data;
    },
    onSuccess: (clip) => {
      queryClient.invalidateQueries({ queryKey: ['clips', id] });
      queryClient.invalidateQueries({
        queryKey: ['projects', clip.project_id, 'clips'],
      });
    },
  });
}

/**
 * Deletes a clip and invalidates its parent project's clips list. Reads the
 * clip's `project_id` from the react-query cache (populated by `useClip`)
 * rather than issuing an extra fetch before the delete.
 */
export function useDeleteClip(id: number | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<void> => {
      await api.delete(`/clips/${id}`);
    },
    onSuccess: () => {
      const cached = queryClient.getQueryData<Clip>(['clips', id]);
      queryClient.invalidateQueries({
        predicate: (query) => {
          const [root, projectId, sub] = query.queryKey;
          if (root !== 'projects' || sub !== 'clips') return false;
          return cached ? projectId === cached.project_id : true;
        },
      });
      queryClient.removeQueries({ queryKey: ['clips', id] });
    },
  });
}
