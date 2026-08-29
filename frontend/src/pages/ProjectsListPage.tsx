import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { GradientButton } from '@/components/ui/GradientButton';
import { GlassCard } from '@/components/ui/GlassCard';
import { AnimatedList } from '@/components/ui/AnimatedList';
import { ProjectCard } from '@/components/projects/ProjectCard';
import { useProjects } from '@/hooks/useProjects';

export default function ProjectsListPage() {
  const navigate = useNavigate();
  const { data: projects, isLoading, isError } = useProjects();

  return (
    <PageWrapper>
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Projects</h1>
            <p className="mt-1 text-sm text-gray-500">
              Turn your long-form videos into short, shareable clips.
            </p>
          </div>
          <GradientButton onClick={() => navigate('/projects/new')}>
            New Project
          </GradientButton>
        </div>

        {isLoading && (
          <p className="text-center text-sm text-gray-500">
            Loading projects…
          </p>
        )}

        {isError && (
          <GlassCard>
            <p className="text-center text-red-500">
              Couldn&apos;t load your projects. Please try again.
            </p>
          </GlassCard>
        )}

        {!isLoading && !isError && projects && projects.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <GlassCard className="flex flex-col items-center gap-4 py-16 text-center">
              <h2 className="text-lg font-semibold text-gray-700">
                No projects yet
              </h2>
              <p className="max-w-sm text-sm text-gray-500">
                Upload a long-form video or paste a URL to start generating
                short clips automatically.
              </p>
              <GradientButton onClick={() => navigate('/projects/new')}>
                Create your first project
              </GradientButton>
            </GlassCard>
          </motion.div>
        )}

        {!isLoading && !isError && projects && projects.length > 0 && (
          <AnimatedList className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </AnimatedList>
        )}
      </div>
    </PageWrapper>
  );
}
