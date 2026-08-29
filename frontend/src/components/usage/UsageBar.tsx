import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface UsageBarProps {
  label: string;
  used: number;
  limit: number;
  className?: string;
}

/** Ratio thresholds at which the fill color shifts toward a warning tone. */
const WARNING_RATIO = 0.7;
const DANGER_RATIO = 0.9;

function fillColorClass(ratio: number): string {
  if (ratio >= DANGER_RATIO) return 'bg-gradient-to-r from-red-500 to-red-600';
  if (ratio >= WARNING_RATIO)
    return 'bg-gradient-to-r from-amber-400 to-orange-500';
  return 'bg-gradient-to-r from-purple-500 to-pink-500';
}

function textColorClass(ratio: number): string {
  if (ratio >= DANGER_RATIO) return 'text-red-600';
  if (ratio >= WARNING_RATIO) return 'text-orange-600';
  return 'text-gray-500';
}

export function UsageBar({ label, used, limit, className }: UsageBarProps) {
  const ratio = limit > 0 ? used / limit : 0;
  const fillPercent = Math.min(Math.max(ratio, 0), 1) * 100;
  const isOverLimit = limit > 0 && used > limit;

  return (
    <div className={cn('w-full', className)}>
      <div className="mb-1.5 flex items-center justify-between text-sm">
        <span className="font-medium text-gray-700">{label}</span>
        <span className={cn('font-medium tabular-nums', textColorClass(ratio))}>
          {used.toLocaleString()} / {limit.toLocaleString()}
          {isOverLimit && ' (over limit)'}
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-white/30">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${fillPercent}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className={cn('h-full rounded-full', fillColorClass(ratio))}
        />
      </div>
    </div>
  );
}
