import { PageWrapper } from '@/components/layout/PageWrapper';
import { MeshBackground } from '@/components/layout/MeshBackground';
import { GlassCard } from '@/components/ui/GlassCard';
import { RegisterForm } from '@/components/auth/RegisterForm';

export default function RegisterPage() {
  return (
    <PageWrapper>
      <MeshBackground />
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="mb-6 text-center">
            <h1 className="text-3xl font-bold text-gray-800">
              Create your account
            </h1>
            <p className="mt-1 text-gray-500">
              Turn long-form videos into shorts in minutes
            </p>
          </div>
          <GlassCard>
            <RegisterForm />
          </GlassCard>
        </div>
      </div>
    </PageWrapper>
  );
}
