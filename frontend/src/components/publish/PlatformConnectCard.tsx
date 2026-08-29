import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { useConnectPlatform, useDisconnectPlatform } from '@/hooks/usePublish';
import { Platform, PublishConnection } from '@/types';

const PLATFORM_LABELS: Record<Platform, string> = {
  tiktok: 'TikTok',
  instagram: 'Instagram',
  youtube_shorts: 'YouTube Shorts',
};

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

interface PlatformConnectCardProps {
  platform: Platform;
  connection: PublishConnection | undefined;
  className?: string;
}

export function PlatformConnectCard({
  platform,
  connection,
  className,
}: PlatformConnectCardProps) {
  const connectMutation = useConnectPlatform();
  const disconnectMutation = useDisconnectPlatform();

  const isConnected = connection !== undefined;

  return (
    <GlassCard className={className}>
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-800">
            {PLATFORM_LABELS[platform]}
          </h3>
          <span
            className={
              isConnected
                ? 'inline-flex items-center rounded-full border border-emerald-200 bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700'
                : 'inline-flex items-center rounded-full border border-gray-200 bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600'
            }
          >
            {isConnected ? 'Connected' : 'Not connected'}
          </span>
        </div>

        {isConnected ? (
          <>
            <div className="text-sm text-gray-500">
              <p className="font-medium text-gray-700">
                {connection.account_handle ?? 'Unknown account'}
              </p>
              <p>Connected {formatDate(connection.connected_at)}</p>
            </div>
            <GradientButton
              type="button"
              disabled={disconnectMutation.isPending}
              onClick={() => disconnectMutation.mutate(connection.id)}
              className="w-full bg-gradient-to-r from-gray-500 to-gray-600"
            >
              {disconnectMutation.isPending ? 'Disconnecting...' : 'Disconnect'}
            </GradientButton>
          </>
        ) : (
          <GradientButton
            type="button"
            disabled={connectMutation.isPending}
            onClick={() => connectMutation.mutate(platform)}
            className="w-full"
          >
            {connectMutation.isPending ? 'Connecting...' : 'Connect'}
          </GradientButton>
        )}

        {disconnectMutation.isError && (
          <p className="text-sm text-red-500">
            Failed to disconnect. Please try again.
          </p>
        )}
        {connectMutation.isError && (
          <p className="text-sm text-red-500">
            Failed to start connection. Please try again.
          </p>
        )}
      </div>
    </GlassCard>
  );
}
