import { GlassCard } from '@/components/ui/GlassCard';
import { Clip } from '@/types';

interface TranscriptPanelProps {
  clip: Clip;
}

export function TranscriptPanel({ clip }: TranscriptPanelProps) {
  return (
    <GlassCard>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
        Transcript
      </h2>
      {clip.transcript_snippet ? (
        <p className="whitespace-pre-wrap text-base leading-relaxed text-gray-700">
          {clip.transcript_snippet}
        </p>
      ) : (
        <p className="text-sm text-gray-400">No transcript available yet.</p>
      )}
    </GlassCard>
  );
}
