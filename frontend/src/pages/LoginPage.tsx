import { PageWrapper } from '@/components/layout/PageWrapper';
import { MeshBackground } from '@/components/layout/MeshBackground';
import { GlassCard } from '@/components/ui/GlassCard';
import { LoginForm } from '@/components/auth/LoginForm';

export default function LoginPage() {
  return (
    <PageWrapper>
      <MeshBackground />
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="mb-6 text-center">
            <h1 className="text-3xl font-bold text-gray-800">Welcome back</h1>
            <p className="mt-1 text-gray-500">
              Sign in to continue to ClipForge
            </p>
          </div>
          <GlassCard>
            <LoginForm />
          </GlassCard>
        </div>
      </div>
    </PageWrapper>
  );
}
