import { useNavigate } from 'react-router-dom';
import { PageWrapper } from '@/components/layout/PageWrapper';
import { GlassCard } from '@/components/ui/GlassCard';
import { GradientButton } from '@/components/ui/GradientButton';
import { useAuth } from '@/context/AuthContext';

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <PageWrapper>
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-md">
          <h1 className="mb-6 text-center text-3xl font-bold text-gray-800">
            Your Profile
          </h1>
          <GlassCard>
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-r from-purple-500 to-pink-500 text-2xl font-semibold text-white">
                {(user?.full_name ?? user?.email ?? '?').charAt(0).toUpperCase()}
              </div>

              <div>
                <p className="text-lg font-semibold text-gray-800">
                  {user?.full_name ?? 'No name set'}
                </p>
                <p className="text-sm text-gray-500">{user?.email}</p>
              </div>

              <div className="w-full space-y-2 rounded-xl bg-white/30 p-4 text-left text-sm text-gray-600">
                <div className="flex justify-between">
                  <span className="font-medium">Account status</span>
                  <span>{user?.is_active ? 'Active' : 'Inactive'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="font-medium">Email verified</span>
                  <span>{user?.is_verified ? 'Yes' : 'No'}</span>
                </div>
              </div>

              <GradientButton onClick={handleLogout} className="w-full">
                Log Out
              </GradientButton>
            </div>
          </GlassCard>
        </div>
      </div>
    </PageWrapper>
  );
}
