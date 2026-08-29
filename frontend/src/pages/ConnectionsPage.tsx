import { PageWrapper } from '@/components/layout/PageWrapper';
import { PlatformConnectCard } from '@/components/publish/PlatformConnectCard';
import { useConnections } from '@/hooks/usePublish';
import { Platform, PublishConnection } from '@/types';

const PLATFORMS: Platform[] = ['tiktok', 'instagram', 'youtube_shorts'];

export default function ConnectionsPage() {
  const { data: connections, isLoading, isError } = useConnections();

  const connectionByPlatform = new Map<Platform, PublishConnection>(
    (connections ?? []).map((connection) => [connection.platform, connection])
  );

  return (
    <PageWrapper>
      <div className="mx-auto max-w-4xl px-4 py-12">
        <h1 className="mb-2 text-3xl font-bold text-gray-800">
          Platform Connections
        </h1>
        <p className="mb-8 text-gray-500">
          Connect your social accounts to publish clips directly from
          ClipForge.
        </p>

        {isLoading && (
          <p className="text-center text-sm text-gray-500">
            Loading connections...
          </p>
        )}

        {isError && (
          <p className="text-center text-sm text-red-500">
            Failed to load connections. Please refresh the page.
          </p>
        )}

        {!isLoading && !isError && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {PLATFORMS.map((platform) => (
              <PlatformConnectCard
                key={platform}
                platform={platform}
                connection={connectionByPlatform.get(platform)}
              />
            ))}
          </div>
        )}
      </div>
    </PageWrapper>
  );
}
