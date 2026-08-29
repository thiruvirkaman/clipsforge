import { NavLink, Outlet } from 'react-router-dom';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { cn } from '@/lib/utils';

interface SettingsNavItem {
  to: string;
  label: string;
}

// Connections/Scheduled Posts (social publishing) are MVP-disabled -- see
// app/services/publish_service.py -- so they're intentionally left out here.
const SETTINGS_NAV_ITEMS: SettingsNavItem[] = [
  { to: '/profile', label: 'Profile' },
  { to: '/settings/usage', label: 'Usage' },
];

/**
 * Shell for the settings area: side/top nav plus an `<Outlet />` for the
 * active settings sub-page. Mounted once at `/settings` and nested routes
 * (added by other modules) render inside it.
 */
export function SettingsLayout() {
  return (
    <PageWrapper>
      <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-10 sm:px-6 lg:flex-row lg:px-8">
        <nav className="flex shrink-0 gap-2 overflow-x-auto pb-2 lg:w-56 lg:flex-col lg:overflow-visible lg:pb-0">
          {SETTINGS_NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/settings'}
              className={({ isActive }) =>
                cn(
                  'whitespace-nowrap rounded-xl px-4 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg'
                    : 'text-gray-600 hover:bg-white/40'
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="min-w-0 flex-1">
          <Outlet />
        </div>
      </div>
    </PageWrapper>
  );
}
