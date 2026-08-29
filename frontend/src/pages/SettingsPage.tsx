import { Link } from 'react-router-dom';
import { GlassCard } from '@/components/ui/GlassCard';

interface SettingsSection {
  to: string;
  title: string;
  description: string;
}

const SETTINGS_SECTIONS: SettingsSection[] = [
  {
    to: '/profile',
    title: 'Profile',
    description: 'Update your name and account details.',
  },
  {
    to: '/settings/connections',
    title: 'Connections',
    description: 'Manage the social accounts you publish clips to.',
  },
  {
    to: '/settings/scheduled-posts',
    title: 'Scheduled Posts',
    description: 'Review your upcoming and past scheduled posts.',
  },
  {
    to: '/settings/usage',
    title: 'Usage',
    description: 'Track your plan limits and usage this period.',
  },
];

/**
 * Settings landing page, rendered as the `/settings` index route inside
 * `SettingsLayout` (which already provides the `PageWrapper` and nav).
 */
export default function SettingsPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-800">Settings</h1>
      <p className="mt-1 text-gray-500">
        Manage your account, connections, scheduled posts, and usage.
      </p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {SETTINGS_SECTIONS.map((section) => (
          <Link key={section.to} to={section.to} className="block">
            <GlassCard className="h-full transition-shadow hover:shadow-2xl">
              <h2 className="text-lg font-semibold text-gray-800">
                {section.title}
              </h2>
              <p className="mt-2 text-sm text-gray-500">
                {section.description}
              </p>
            </GlassCard>
          </Link>
        ))}
      </div>
    </div>
  );
}
