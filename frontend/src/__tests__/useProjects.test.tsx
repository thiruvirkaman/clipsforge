import { describe, test, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import {
  useProjects,
  useCreateProject,
  useDeleteProject,
} from '@/hooks/useProjects';
import api from '@/services/api';
import type { Project } from '@/types';

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api, true);

function buildProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 1,
    user_id: 1,
    title: 'Test Project',
    source_type: 'upload',
    source_url: null,
    source_file_path: '/uploads/a.mp4',
    duration_seconds: 60,
    status: 'ready',
    error_message: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    ...overrides,
  };
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useProjects', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('fetches and returns the list of projects', async () => {
    const projects = [buildProject({ id: 1 }), buildProject({ id: 2 })];
    mockedApi.get.mockResolvedValueOnce({ data: projects });

    const { result } = renderHook(() => useProjects(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockedApi.get).toHaveBeenCalledWith('/projects');
    expect(result.current.data).toEqual(projects);
  });

  test('surfaces a fetch error', async () => {
    mockedApi.get.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useProjects(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe('useCreateProject', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('posts multipart form data and invalidates the projects list', async () => {
    const created = buildProject({ id: 3, title: 'New Project' });
    mockedApi.post.mockResolvedValueOnce({ data: created });

    const { result } = renderHook(() => useCreateProject(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      title: 'New Project',
      source_type: 'url',
      source_url: 'https://example.com/video',
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockedApi.post).toHaveBeenCalledWith(
      '/projects',
      expect.any(FormData),
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    expect(result.current.data).toEqual(created);
  });
});

describe('useDeleteProject', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('deletes a project by id', async () => {
    mockedApi.delete.mockResolvedValueOnce({ data: undefined });

    const { result } = renderHook(() => useDeleteProject(), {
      wrapper: createWrapper(),
    });

    result.current.mutate(42);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockedApi.delete).toHaveBeenCalledWith('/projects/42');
  });
});
