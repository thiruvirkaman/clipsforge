import { motion } from 'framer-motion';
import { AnimatedInput } from '@/components/ui/AnimatedInput';
import { cn } from '@/lib/utils';
import { SourceType } from '@/types';

interface SourceModeToggleProps {
  mode: SourceType;
  onModeChange: (mode: SourceType) => void;
}

/** Tab toggle switching the new-project form between upload and URL modes. */
export function SourceModeToggle({ mode, onModeChange }: SourceModeToggleProps) {
  const tabs: { value: SourceType; label: string }[] = [
    { value: 'upload', label: 'Upload file' },
    { value: 'url', label: 'Paste URL' },
  ];

  return (
    <div className="inline-flex rounded-full border border-gray-200 bg-gray-50 p-1">
      {tabs.map((tab) => (
        <motion.button
          key={tab.value}
          type="button"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => onModeChange(tab.value)}
          className={cn(
            'rounded-full px-4 py-2 text-sm font-medium transition-colors',
            mode === tab.value
              ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow'
              : 'text-gray-500 hover:text-gray-700'
          )}
        >
          {tab.label}
        </motion.button>
      ))}
    </div>
  );
}

interface UrlInputFormProps {
  url: string;
  onUrlChange: (url: string) => void;
  error?: string;
}

export function UrlInputForm({ url, onUrlChange, error }: UrlInputFormProps) {
  return (
    <AnimatedInput
      type="url"
      label="Video URL"
      placeholder="https://youtube.com/watch?v=..."
      value={url}
      onChange={(event) => onUrlChange(event.target.value)}
      error={error}
      autoComplete="off"
    />
  );
}
