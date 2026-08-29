import { PageWrapper } from '@/components/layout/PageWrapper';
import { GlassCard } from '@/components/ui/GlassCard';
import { PlanLimitCard } from '@/components/usage/PlanLimitCard';
import { useUsageSummary, useUsageHistory } from '@/hooks/useUsage';

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function UsagePage() {
  const {
    data: summary,
    isLoading: isSummaryLoading,
    isError: isSummaryError,
  } = useUsageSummary();
  const {
    data: history,
    isLoading: isHistoryLoading,
    isError: isHistoryError,
  } = useUsageHistory();

  return (
    <PageWrapper>
      <div className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="mb-6 text-3xl font-bold text-gray-800">
          Usage &amp; Billing
        </h1>

        {isSummaryLoading && (
          <GlassCard>
            <p className="text-sm text-gray-500">Loading plan usage...</p>
          </GlassCard>
        )}
        {isSummaryError && (
          <GlassCard>
            <p className="text-sm text-red-500">
              Failed to load your plan usage. Please try again later.
            </p>
          </GlassCard>
        )}
        {summary && <PlanLimitCard summary={summary} />}

        <div className="mt-8">
          <h2 className="mb-3 text-lg font-semibold text-gray-800">
            Recent Usage
          </h2>
          <GlassCard>
            {isHistoryLoading && (
              <p className="text-sm text-gray-500">Loading history...</p>
            )}
            {isHistoryError && (
              <p className="text-sm text-red-500">
                Failed to load usage history. Please try again later.
              </p>
            )}
            {history && history.length === 0 && (
              <p className="text-sm text-gray-500">
                No usage recorded yet.
              </p>
            )}
            {history && history.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-white/20 text-gray-500">
                      <th className="pb-2 font-medium">Date</th>
                      <th className="pb-2 font-medium">Project</th>
                      <th className="pb-2 text-right font-medium">Minutes</th>
                      <th className="pb-2 text-right font-medium">Clips</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((entry) => (
                      <tr
                        key={entry.id}
                        className="border-b border-white/10 text-gray-700 last:border-0"
                      >
                        <td className="py-2">{formatDate(entry.recorded_at)}</td>
                        <td className="py-2">
                          {entry.project_id !== null
                            ? `#${entry.project_id}`
                            : '—'}
                        </td>
                        <td className="py-2 text-right tabular-nums">
                          {entry.minutes_processed.toLocaleString()}
                        </td>
                        <td className="py-2 text-right tabular-nums">
                          {entry.clips_generated.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </GlassCard>
        </div>
      </div>
    </PageWrapper>
  );
}
