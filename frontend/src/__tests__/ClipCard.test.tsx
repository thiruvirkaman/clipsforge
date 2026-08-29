import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ClipCard } from '@/components/clips/ClipCard';
import type { Clip } from '@/types';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual =
    await vi.importActual<typeof import('react-router-dom')>(
      'react-router-dom'
    );
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// ClipCard fetches its thumbnail through the authenticated API client (blob
// URL, no public/static media mount) -- stub the hook so tests don't need a
// real network round-trip.
vi.mock('@/hooks/useAuthenticatedMedia', () => ({
  useAuthenticatedMediaUrl: (path: string | null | undefined) =>
    path ? `blob:mock/${path}` : null,
}));

function buildClip(overrides: Partial<Clip> = {}): Clip {
  return {
    id: 42,
    project_id: 1,
    user_id: 1,
    title: 'A great highlight moment',
    start_time: 10,
    end_time: 37,
    transcript_snippet: 'Something insightful was said here.',
    relevance_score: 0.92,
    aspect_ratio: '9:16',
    caption_style: null,
    status: 'ready',
    video_file_path: '/videos/clip-42.mp4',
    thumbnail_path: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    ...overrides,
  };
}

function renderClipCard(clip: Clip) {
  return render(
    <MemoryRouter>
      <ClipCard clip={clip} />
    </MemoryRouter>
  );
}

describe('ClipCard', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
  });

  test('renders the clip title and formatted duration', () => {
    renderClipCard(buildClip());
    expect(screen.getByText('A great highlight moment')).toBeInTheDocument();
    expect(screen.getByText('27s')).toBeInTheDocument();
  });

  test('shows a placeholder when there is no thumbnail', () => {
    renderClipCard(buildClip({ thumbnail_path: null }));
    expect(screen.getByText(/no preview yet/i)).toBeInTheDocument();
  });

  test('renders the thumbnail image via the authenticated media URL', () => {
    renderClipCard(buildClip({ id: 42, thumbnail_path: 'clip-42-thumb.jpg' }));
    const img = screen.getByRole('img', { name: 'A great highlight moment' });
    // ClipCard fetches thumbnails through the authenticated API route (no
    // public/static media mount), not the raw stored filename.
    expect(img).toHaveAttribute('src', expect.stringContaining('/clips/42/thumbnail'));
  });

  test.each([
    ['queued', 'Queued'],
    ['rendering', 'Rendering'],
    ['ready', 'Ready'],
    ['failed', 'Failed'],
  ] as const)('shows the "%s" status pill as "%s"', (status, label) => {
    renderClipCard(buildClip({ status }));
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  test.each(['queued', 'rendering'] as const)(
    'pulses the status pill while the clip is in status "%s"',
    (status) => {
      const { container } = renderClipCard(buildClip({ status }));
      expect(container.querySelector('.animate-ping')).toBeTruthy();
    }
  );

  test.each(['ready', 'failed'] as const)(
    'does not pulse the status pill once the clip reaches status "%s"',
    (status) => {
      const { container } = renderClipCard(buildClip({ status }));
      expect(container.querySelector('.animate-ping')).toBeFalsy();
    }
  );

  test('navigates to the clip detail page when clicked', async () => {
    const user = userEvent.setup();
    renderClipCard(buildClip({ id: 99 }));

    await user.click(screen.getByRole('button'));

    expect(mockNavigate).toHaveBeenCalledWith('/clips/99');
  });

  test('navigates to the clip detail page on Enter key', async () => {
    const user = userEvent.setup();
    renderClipCard(buildClip({ id: 7 }));

    screen.getByRole('button').focus();
    await user.keyboard('{Enter}');

    expect(mockNavigate).toHaveBeenCalledWith('/clips/7');
  });
});
