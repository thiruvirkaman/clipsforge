import { describe, test, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { UsageBar } from '@/components/usage/UsageBar';

function getFillBar(container: HTMLElement): HTMLElement {
  const bar = container.querySelector('.h-2\\.5 > div');
  if (!bar) throw new Error('fill bar not found');
  return bar as HTMLElement;
}

describe('UsageBar', () => {
  test('renders the label and used/limit counts', () => {
    render(<UsageBar label="Minutes" used={30} limit={100} />);
    expect(screen.getByText('Minutes')).toBeInTheDocument();
    expect(screen.getByText('30 / 100')).toBeInTheDocument();
  });

  test('uses the default (safe) fill color below the warning threshold', () => {
    const { container } = render(
      <UsageBar label="Minutes" used={50} limit={100} />
    );
    expect(getFillBar(container).className).toContain('from-purple-500');
  });

  test('switches to the warning fill color at/above 70% usage', () => {
    const { container } = render(
      <UsageBar label="Minutes" used={70} limit={100} />
    );
    expect(getFillBar(container).className).toContain('from-amber-400');
  });

  test('switches to the danger fill color at/above 90% usage', () => {
    const { container } = render(
      <UsageBar label="Minutes" used={95} limit={100} />
    );
    expect(getFillBar(container).className).toContain('from-red-500');
  });

  test('shows an over-limit indicator and the danger fill color when usage exceeds the limit', () => {
    const { container } = render(
      <UsageBar label="Minutes" used={150} limit={100} />
    );
    expect(getFillBar(container).className).toContain('from-red-500');
    expect(screen.getByText(/over limit/i)).toBeInTheDocument();
  });

  test('does not divide by zero when limit is 0', () => {
    render(<UsageBar label="Minutes" used={0} limit={0} />);
    expect(screen.getByText('0 / 0')).toBeInTheDocument();
    expect(screen.queryByText(/over limit/i)).not.toBeInTheDocument();
  });

  test('formats large numbers with thousands separators', () => {
    render(<UsageBar label="Minutes" used={1234} limit={5000} />);
    expect(screen.getByText('1,234 / 5,000')).toBeInTheDocument();
  });
});
