import { useParams, useNavigate } from 'react-router-dom';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { StatusBadge } from '@/components/projects/StatusBadge';
import { ProcessingProgress } from '@/components/projects/ProcessingProgress';
import { ClipsGrid } from '@/components/clips/ClipsGrid';
import { useProject, useStartProcessing } from '@/hooks/useProjects';

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const projectId = id ? Number(id) : undefined;

  const { data: project, isLoading, isError } = useProject(projectId);
  const startProcessing = useStartProcessing(projectId);

  if (isLoading) {
    return (
      <PageWrapper>
        <div className="mx-auto max-w-4xl px-6 py-10">
          <p className="text-center text-sm text-gray-500">
            Loading project…
          </p>
        </div>
      </PageWrapper>
    );
  }

  if (isError || !project) {
    return (
      <PageWrapper>
        <div className="mx-auto max-w-4xl px-6 py-10">
          <GlassCard>
            <p className="text-center text-red-500">
              Couldn&apos;t load this project.
            </p>
            <div className="mt-4 flex justify-center">
              <GradientButton onClick={() => navigate('/projects')}>
                Back to Projects
              </GradientButton>
            </div>
          </GlassCard>
        </div>
      </PageWrapper>
    );
  }

  const isProcessing = project.status !== 'ready' && project.status !== 'failed';

  return (
    <PageWrapper>
      <div className="mx-auto max-w-4xl px-6 py-10">
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">
              {project.title}
            </h1>
            <div className="mt-2">
              <StatusBadge status={project.status} />
            </div>
          </div>
          {project.status === 'failed' && (
            <GradientButton
              onClick={() => startProcessing.mutate(undefined)}
              disabled={startProcessing.isPending}
            >
              {startProcessing.isPending ? 'Retrying…' : 'Retry Processing'}
            </GradientButton>
          )}
        </div>

        {project.status === 'failed' && project.error_message && (
          <GlassCard className="mb-6">
            <p className="text-sm text-red-500">{project.error_message}</p>
          </GlassCard>
        )}

        {isProcessing && (
          <div className="mb-6">
            <ProcessingProgress
              projectId={project.id}
              projectStatus={project.status}
            />
          </div>
        )}

        {project.status !== 'failed' && <ClipsGrid projectId={project.id} />}
      </div>
    </PageWrapper>
  );
}
