import { PageWrapper } from '@/components/layout/PageWrapper';
import { NewProjectCTA } from '@/components/dashboard/NewProjectCTA';
import { RecentProjects } from '@/components/dashboard/RecentProjects';
import { UsageSummary } from '@/components/dashboard/UsageSummary';
import { useAuth } from '@/context/AuthContext';

export default function DashboardPage() {
  const { user } = useAuth();
  const displayName = user?.full_name?.split(' ')[0] ?? user?.email ?? 'there';

  return (
    <PageWrapper>
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <h1 className="text-3xl font-bold text-gray-800">
          Welcome back, {displayName}
        </h1>
        <p className="mt-1 text-gray-500">
          Here&apos;s what&apos;s happening with your clips.
        </p>

        <div className="mt-8">
          <NewProjectCTA />
        </div>

        <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <RecentProjects />
          </div>
          <div>
            <UsageSummary />
          </div>
        </div>
      </div>
    </PageWrapper>
  );
}
