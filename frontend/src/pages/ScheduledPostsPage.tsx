import { PageWrapper } from '@/components/layout/PageWrapper';
import { PostStatusTable } from '@/components/publish/PostStatusTable';
import { useScheduledPosts } from '@/hooks/usePublish';

export default function ScheduledPostsPage() {
  const { data: posts, isLoading, isError } = useScheduledPosts();

  return (
    <PageWrapper>
      <div className="mx-auto max-w-3xl px-4 py-12">
        <h1 className="mb-2 text-3xl font-bold text-gray-800">
          Scheduled Posts
        </h1>
        <p className="mb-8 text-gray-500">
          Track the status of clips you've published or scheduled to social
          platforms.
        </p>

        {isLoading && (
          <p className="text-center text-sm text-gray-500">
            Loading scheduled posts...
          </p>
        )}

        {isError && (
          <p className="text-center text-sm text-red-500">
            Failed to load scheduled posts. Please refresh the page.
          </p>
        )}

        {!isLoading && !isError && <PostStatusTable posts={posts ?? []} />}
      </div>
    </PageWrapper>
  );
}
