import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { GlassCard } from '@/components/ui/GlassCard';
import { AnimatedInput } from '@/components/ui/AnimatedInput';
import { GradientButton } from '@/components/ui/GradientButton';
import { UploadDropzone } from '@/components/projects/UploadDropzone';
import { SourceModeToggle, UrlInputForm } from '@/components/projects/UrlInputForm';
import { useCreateProject, useStartProcessing } from '@/hooks/useProjects';
import { SourceType } from '@/types';

interface FormErrors {
  title?: string;
  source?: string;
  form?: string;
}

function extractErrorMessage(error: unknown): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response?: { data?: { detail?: unknown } } })
      .response === 'object'
  ) {
    const detail = (error as { response?: { data?: { detail?: unknown } } })
      .response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return 'Unable to create project. Please try again.';
}

export default function NewProjectPage() {
  const navigate = useNavigate();
  const createProject = useCreateProject();

  const [title, setTitle] = useState('');
  const [mode, setMode] = useState<SourceType>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // useStartProcessing needs the created project's id, which we only know
  // after the create mutation resolves — call it lazily via mutateAsync
  // inside handleSubmit instead of binding it to a fixed id up front.
  const startProcessing = useStartProcessing(undefined);

  const validate = (): boolean => {
    const nextErrors: FormErrors = {};
    if (!title.trim()) {
      nextErrors.title = 'Title is required';
    }
    if (mode === 'upload' && !file) {
      nextErrors.source = 'Please select a video file to upload';
    }
    if (mode === 'url' && !url.trim()) {
      nextErrors.source = 'Please paste a video URL';
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!validate()) return;

    setIsSubmitting(true);
    setErrors({});
    try {
      const project = await createProject.mutateAsync({
        title: title.trim(),
        source_type: mode,
        source_url: mode === 'url' ? url.trim() : undefined,
        file: mode === 'upload' ? (file ?? undefined) : undefined,
      });

      try {
        await startProcessing.mutateAsync(project.id);
      } catch {
        // Processing kickoff failing shouldn't block navigation — the
        // detail page lets the user retry from there.
      }

      navigate(`/projects/${project.id}`);
    } catch (error) {
      setErrors({ form: extractErrorMessage(error) });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageWrapper>
      <div className="mx-auto max-w-2xl px-6 py-10">
        <h1 className="mb-8 text-2xl font-bold text-gray-800">
          New Project
        </h1>

        <GlassCard>
          <form onSubmit={handleSubmit} className="space-y-6" noValidate>
            <AnimatedInput
              label="Title"
              placeholder="My awesome podcast episode"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              error={errors.title}
            />

            <div>
              <label className="mb-2 block text-sm font-medium">
                Video source
              </label>
              <SourceModeToggle mode={mode} onModeChange={setMode} />
            </div>

            {mode === 'upload' ? (
              <UploadDropzone
                file={file}
                onFileSelect={setFile}
                error={errors.source}
              />
            ) : (
              <UrlInputForm
                url={url}
                onUrlChange={setUrl}
                error={errors.source}
              />
            )}

            {errors.form && (
              <p className="text-sm text-red-500" role="alert">
                {errors.form}
              </p>
            )}

            <GradientButton
              type="submit"
              disabled={isSubmitting}
              className="w-full"
            >
              {isSubmitting ? 'Creating…' : 'Create Project'}
            </GradientButton>
          </form>
        </GlassCard>
      </div>
    </PageWrapper>
  );
}
