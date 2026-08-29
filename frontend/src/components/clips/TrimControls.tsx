import { useState } from 'react';
import { AnimatedInput } from '@/components/ui/AnimatedInput';
import { GradientButton } from '@/components/ui/GradientButton';
import { useRegenerateClip } from '@/hooks/useClips';
import { Clip } from '@/types';

interface TrimControlsProps {
  clip: Clip;
}

export function TrimControls({ clip }: TrimControlsProps) {
  const [startTime, setStartTime] = useState(clip.start_time);
  const [endTime, setEndTime] = useState(clip.end_time);
  const regenerateClip = useRegenerateClip(clip.id);

  const isValidRange = endTime > startTime && startTime >= 0;
  const isUnchanged =
    startTime === clip.start_time && endTime === clip.end_time;

  const handleRegenerate = () => {
    if (!isValidRange) return;
    regenerateClip.mutate({ start_time: startTime, end_time: endTime });
  };

  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
        Trim &amp; Regenerate
      </h2>
      <div className="grid grid-cols-2 gap-4">
        <AnimatedInput
          type="number"
          label="Start time (s)"
          min={0}
          step={0.1}
          value={startTime}
          onChange={(event) => setStartTime(Number(event.target.value))}
        />
        <AnimatedInput
          type="number"
          label="End time (s)"
          min={0}
          step={0.1}
          value={endTime}
          onChange={(event) => setEndTime(Number(event.target.value))}
        />
      </div>

      {!isValidRange && (
        <p className="mt-2 text-sm text-red-500">
          End time must be greater than start time.
        </p>
      )}

      {regenerateClip.isError && (
        <p className="mt-2 text-sm text-red-500">
          Failed to regenerate this clip. Please try again.
        </p>
      )}

      <GradientButton
        type="button"
        className="mt-4"
        disabled={!isValidRange || isUnchanged || regenerateClip.isPending}
        onClick={handleRegenerate}
      >
        {regenerateClip.isPending ? 'Regenerating…' : 'Regenerate'}
      </GradientButton>
    </div>
  );
}
