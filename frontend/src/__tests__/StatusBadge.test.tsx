import { describe, test, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge } from '@/components/projects/StatusBadge';

describe('StatusBadge', () => {
  test('renders the human-readable label for a project status', () => {
    render(<StatusBadge status="ready" />);
    expect(screen.getByText('Ready')).toBeInTheDocument();
  });

  test('renders the human-readable label for a job status', () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByText('Running')).toBeInTheDocument();
  });

  test('applies a distinct color class for failed statuses', () => {
    render(<StatusBadge status="failed" />);
    const badge = screen.getByText('Failed');
    expect(badge.className).toContain('bg-red-100');
    expect(badge.className).toContain('text-red-700');
  });

  test('applies a distinct color class for ready/completed statuses', () => {
    render(<StatusBadge status="completed" />);
    const badge = screen.getByText('Completed');
    expect(badge.className).toContain('bg-emerald-100');
  });

  test.each(['pending', 'transcribing', 'analyzing', 'running', 'queued'] as const)(
    'shows a pulsing indicator for the in-progress status "%s"',
    (status) => {
      const { container } = render(<StatusBadge status={status} />);
      expect(container.querySelector('.animate-ping')).toBeTruthy();
    }
  );

  test.each(['ready', 'failed', 'completed'] as const)(
    'does not show a pulsing indicator for the terminal status "%s"',
    (status) => {
      const { container } = render(<StatusBadge status={status} />);
      expect(container.querySelector('.animate-ping')).toBeFalsy();
    }
  );

  test('applies an extra className when provided', () => {
    render(<StatusBadge status="ready" className="ml-2" />);
    expect(screen.getByText('Ready').className).toContain('ml-2');
  });
});
