import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';
import { Project, ProcessingJob, SourceType } from '@/types';

/** Project statuses that indicate a background job is still running. */
const PROCESSING_STATUSES: ReadonlySet<Project['status']> = new Set([
  'pending',
  'transcribing',
  'analyzing',
]);

const PROJECT_LIST_POLL_MS = 5000;
const PROJECT_DETAIL_POLL_MS = 3000;
const JOBS_POLL_MS = 3000;

/**
 * Lists the current user's projects. Polls periodically while any project
 * in the last-fetched page is still being processed, so cards flip to
 * "ready"/"failed" without a manual refresh.
 */
export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: async (): Promise<Project[]> => {
      const { data } = await api.get<Project[]>('/projects');
      return data;
    },
    refetchInterval: (query) => {
      const projects = query.state.data;
      const hasActiveProject = (projects ?? []).some((project) =>
        PROCESSING_STATUSES.has(project.status)
      );
      return hasActiveProject ? PROJECT_LIST_POLL_MS : false;
    },
  });
}

/**
 * Fetches a single project. Polls while it hasn't reached a terminal
 * status (`ready` or `failed`) so the detail page reflects progress live.
 */
export function useProject(id: number | undefined) {
  return useQuery({
    queryKey: ['projects', id],
    queryFn: async (): Promise<Project> => {
      const { data } = await api.get<Project>(`/projects/${id}`);
      return data;
    },
    enabled: id !== undefined,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!status) return false;
      return status !== 'ready' && status !== 'failed'
        ? PROJECT_DETAIL_POLL_MS
        : false;
    },
  });
}

export interface CreateProjectInput {
  title: string;
  source_type: SourceType;
  source_url?: string;
  file?: File;
}

/** Creates a project via multipart/form-data (upload) or URL source. */
export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateProjectInput): Promise<Project> => {
      const form = new FormData();
      form.append('title', input.title);
      form.append('source_type', input.source_type);
      if (input.source_url) form.append('source_url', input.source_url);
      if (input.file) form.append('file', input.file);

      const { data } = await api.post<Project>('/projects', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number): Promise<void> => {
      await api.delete(`/projects/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });
}

/**
 * Kicks off backend processing (transcription -> highlights -> render) for
 * a project. Accepts an optional id override on `mutate`/`mutateAsync` so
 * callers that only learn the project id at submit time (e.g. right after
 * creating it) aren't forced to know it when the hook is first called.
 */
export function useStartProcessing(id: number | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (overrideId?: number): Promise<Project> => {
      const targetId = overrideId ?? id;
      const { data } = await api.post<Project>(
        `/projects/${targetId}/process`
      );
      return data;
    },
    onSuccess: (_data, overrideId) => {
      const targetId = overrideId ?? id;
      queryClient.invalidateQueries({ queryKey: ['projects', targetId] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      queryClient.invalidateQueries({
        queryKey: ['projects', targetId, 'jobs'],
      });
    },
  });
}

/** Polls a project's processing jobs while any are queued or running. */
export function useProjectJobs(id: number | undefined) {
  return useQuery({
    queryKey: ['projects', id, 'jobs'],
    queryFn: async (): Promise<ProcessingJob[]> => {
      const { data } = await api.get<ProcessingJob[]>(`/projects/${id}/jobs`);
      return data;
    },
    enabled: id !== undefined,
    refetchInterval: (query) => {
      const jobs = query.state.data ?? [];
      const hasActiveJob = jobs.some(
        (job) => job.status === 'queued' || job.status === 'running'
      );
      return hasActiveJob ? JOBS_POLL_MS : false;
    },
  });
}
