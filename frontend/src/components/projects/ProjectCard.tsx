import { useNavigate } from 'react-router-dom';
import { GlassCard } from '@/components/ui/GlassCard';
import { StatusBadge } from '@/components/projects/StatusBadge';
import { Project } from '@/types';

interface ProjectCardProps {
  project: Project;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return 'Unknown length';
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.round(seconds % 60);
  return `${minutes}m ${remaining.toString().padStart(2, '0')}s`;
}

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function ProjectCard({ project }: ProjectCardProps) {
  const navigate = useNavigate();

  const goToDetail = () => navigate(`/projects/${project.id}`);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={goToDetail}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          goToDetail();
        }
      }}
      className="cursor-pointer"
    >
      <GlassCard className="transition-shadow hover:shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <h3 className="line-clamp-2 text-lg font-semibold text-gray-800">
            {project.title}
          </h3>
          <StatusBadge status={project.status} />
        </div>

        <div className="mt-4 flex items-center justify-between text-sm text-gray-500">
          <span>{formatDuration(project.duration_seconds)}</span>
          <span>{formatDate(project.created_at)}</span>
        </div>

        {project.status === 'failed' && project.error_message && (
          <p className="mt-3 line-clamp-2 text-sm text-red-500">
            {project.error_message}
          </p>
        )}
      </GlassCard>
    </div>
  );
}
