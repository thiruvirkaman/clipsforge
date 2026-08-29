import { GlassCard } from '@/components/ui/GlassCard';
import { UsageBar } from '@/components/usage/UsageBar';
import { UsageSummary } from '@/types';

interface PlanLimitCardProps {
  summary: UsageSummary;
  className?: string;
}

const PLAN_LABELS: Record<string, string> = {
  free: 'Free',
  pro: 'Pro',
};

export function PlanLimitCard({ summary, className }: PlanLimitCardProps) {
  const planLabel = PLAN_LABELS[summary.plan_type] ?? summary.plan_type;

  return (
    <GlassCard className={className}>
      <div className="mb-5 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">Plan Usage</h2>
        <span className="rounded-full bg-gradient-to-r from-purple-500 to-pink-500 px-3 py-1 text-xs font-semibold text-white">
          {planLabel}
        </span>
      </div>

      <div className="space-y-5">
        <UsageBar
          label="Minutes processed"
          used={summary.minutes_used_this_period}
          limit={summary.monthly_minutes_limit}
        />
        <UsageBar
          label="Clips generated"
          used={summary.clips_used_this_period}
          limit={summary.monthly_clips_limit}
        />
      </div>
    </GlassCard>
  );
}
