import { Link } from 'react-router-dom';
import { GlassCard } from '@/components/ui/GlassCard';
import { PlanLimitCard } from '@/components/usage/PlanLimitCard';
import { useUsageSummary } from '@/hooks/useUsage';

/** Dashboard widget summarizing the user's plan limits and usage this period. */
export function UsageSummary() {
  const { data: summary, isLoading, isError } = useUsageSummary();

  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-800">Usage</h2>
        <Link
          to="/settings/usage"
          className="text-sm font-medium text-purple-600 transition-colors hover:text-purple-700 hover:underline"
        >
          View details
        </Link>
      </div>

      {isLoading && (
        <GlassCard>
          <p className="text-sm text-gray-500">Loading your usage...</p>
        </GlassCard>
      )}

      {isError && !isLoading && (
        <GlassCard>
          <p className="text-sm text-red-500">
            Couldn&apos;t load your usage. Please try again later.
          </p>
        </GlassCard>
      )}

      {!isLoading && !isError && summary && <PlanLimitCard summary={summary} />}
    </section>
  );
}
