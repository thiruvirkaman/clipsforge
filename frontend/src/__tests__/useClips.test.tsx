import { describe, test, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useClips } from '@/hooks/useClips';
import api from '@/services/api';
import type { Clip } from '@/types';

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api, true);

function buildClip(overrides: Partial<Clip> = {}): Clip {
  return {
    id: 1,
    project_id: 10,
    user_id: 1,
    title: 'Clip',
    start_time: 0,
    end_time: 30,
    transcript_snippet: null,
    relevance_score: null,
    aspect_ratio: '9:16',
    caption_style: null,
    status: 'ready',
    video_file_path: null,
    thumbnail_path: null,
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

describe('useClips', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  test('fetches clips for a project', async () => {
    const clips = [buildClip({ id: 1 }), buildClip({ id: 2 })];
    mockedApi.get.mockResolvedValueOnce({ data: clips });

    const { result } = renderHook(() => useClips(10), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockedApi.get).toHaveBeenCalledWith('/projects/10/clips');
    expect(result.current.data).toEqual(clips);
  });

  test('does not fetch when projectId is undefined', () => {
    const { result } = renderHook(() => useClips(undefined), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockedApi.get).not.toHaveBeenCalled();
  });
});
