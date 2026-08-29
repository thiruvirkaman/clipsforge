import { ChangeEvent, DragEvent, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

interface UploadDropzoneProps {
  file: File | null;
  onFileSelect: (file: File | null) => void;
  error?: string;
  accept?: string;
}

function formatFileSize(bytes: number): string {
  const megabytes = bytes / (1024 * 1024);
  return `${megabytes.toFixed(1)} MB`;
}

export function UploadDropzone({
  file,
  onFileSelect,
  error,
  accept = 'video/*',
}: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragActive, setIsDragActive] = useState(false);

  const handleFiles = (files: FileList | null) => {
    const selected = files?.[0] ?? null;
    onFileSelect(selected);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragActive(false);
    handleFiles(event.dataTransfer.files);
  };

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    handleFiles(event.target.files);
  };

  return (
    <div>
      <motion.div
        whileHover={{ scale: 1.01 }}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragActive(true);
        }}
        onDragLeave={() => setIsDragActive(false)}
        onDrop={handleDrop}
        className={cn(
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors',
          isDragActive
            ? 'border-purple-500 bg-purple-50'
            : 'border-gray-200 hover:border-purple-300',
          error && 'border-red-500'
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleInputChange}
          className="hidden"
        />
        {file ? (
          <>
            <p className="font-medium text-gray-800">{file.name}</p>
            <p className="text-sm text-gray-500">{formatFileSize(file.size)}</p>
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onFileSelect(null);
                if (inputRef.current) inputRef.current.value = '';
              }}
              className="mt-1 text-sm font-medium text-purple-600 hover:underline"
            >
              Remove
            </button>
          </>
        ) : (
          <>
            <p className="font-medium text-gray-700">
              Drag &amp; drop a video, or click to browse
            </p>
            <p className="text-sm text-gray-400">MP4, MOV, or WebM</p>
          </>
        )}
      </motion.div>
      {error && <p className="mt-1 text-sm text-red-500">{error}</p>}
    </div>
  );
}
