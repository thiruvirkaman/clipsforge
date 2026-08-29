import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProjectCard } from '@/components/projects/ProjectCard';
import type { Project } from '@/types';

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

function buildProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 5,
    user_id: 1,
    title: 'My Long Podcast Episode',
    source_type: 'upload',
    source_url: null,
    source_file_path: '/uploads/episode.mp4',
    duration_seconds: 125,
    status: 'ready',
    error_message: null,
    created_at: '2026-03-15T00:00:00Z',
    updated_at: null,
    ...overrides,
  };
}

function renderProjectCard(project: Project) {
  return render(
    <MemoryRouter>
      <ProjectCard project={project} />
    </MemoryRouter>
  );
}

describe('ProjectCard', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
  });

  test('renders the project title and status badge', () => {
    renderProjectCard(buildProject());
    expect(screen.getByText('My Long Podcast Episode')).toBeInTheDocument();
    expect(screen.getByText('Ready')).toBeInTheDocument();
  });

  test('formats the duration in minutes and seconds', () => {
    renderProjectCard(buildProject({ duration_seconds: 125 }));
    expect(screen.getByText('2m 05s')).toBeInTheDocument();
  });

  test('shows "Unknown length" when duration is null', () => {
    renderProjectCard(buildProject({ duration_seconds: null }));
    expect(screen.getByText('Unknown length')).toBeInTheDocument();
  });

  test('shows the error message when the project failed', () => {
    renderProjectCard(
      buildProject({ status: 'failed', error_message: 'Transcoding failed' })
    );
    expect(screen.getByText('Transcoding failed')).toBeInTheDocument();
  });

  test('does not show an error message for non-failed projects', () => {
    renderProjectCard(
      buildProject({ status: 'ready', error_message: 'Transcoding failed' })
    );
    expect(screen.queryByText('Transcoding failed')).not.toBeInTheDocument();
  });

  test('navigates to the project detail page when clicked', async () => {
    const user = userEvent.setup();
    renderProjectCard(buildProject({ id: 5 }));

    await user.click(screen.getByRole('button'));

    expect(mockNavigate).toHaveBeenCalledWith('/projects/5');
  });
});
