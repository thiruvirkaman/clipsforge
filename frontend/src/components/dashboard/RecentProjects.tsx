import { Link } from 'react-router-dom';
import { GlassCard } from '@/components/ui/GlassCard';
import { AnimatedList } from '@/components/ui/AnimatedList';
import { ProjectCard } from '@/components/projects/ProjectCard';
import { useProjects } from '@/hooks/useProjects';

const MAX_RECENT_PROJECTS = 4;

/** Dashboard widget listing the user's most recently created projects. */
export function RecentProjects() {
  const { data: projects, isLoading, isError } = useProjects();

  const recentProjects = (projects ?? [])
    .slice()
    .sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
    .slice(0, MAX_RECENT_PROJECTS);

  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-800">Recent Projects</h2>
        <Link
          to="/projects"
          className="text-sm font-medium text-purple-600 transition-colors hover:text-purple-700 hover:underline"
        >
          View all
        </Link>
      </div>

      {isLoading && (
        <GlassCard>
          <p className="text-sm text-gray-500">Loading your projects...</p>
        </GlassCard>
      )}

      {isError && !isLoading && (
        <GlassCard>
          <p className="text-sm text-red-500">
            Couldn&apos;t load your projects. Please try again later.
          </p>
        </GlassCard>
      )}

      {!isLoading && !isError && recentProjects.length === 0 && (
        <GlassCard>
          <p className="text-sm text-gray-500">
            No projects yet. Create your first one to get started.
          </p>
        </GlassCard>
      )}

      {!isLoading && !isError && recentProjects.length > 0 && (
        <AnimatedList className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {recentProjects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </AnimatedList>
      )}
    </section>
  );
}
