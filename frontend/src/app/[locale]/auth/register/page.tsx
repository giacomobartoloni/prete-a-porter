import { RegisterForm } from '@/components/auth';
import Link from 'next/link';

export default function RegisterPage() {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-serif font-semibold text-text-primary">Crea Account</h1>
          <p className="text-text-secondary mt-1 text-sm">Registrati per iniziare</p>
        </div>

        <div className="bg-bg-card rounded-2xl shadow-subtle border border-border p-8">
          <RegisterForm />
        </div>

        <p className="text-center text-xs text-text-tertiary mt-6">
          Hai già un account?{' '}
          <Link href="/auth/login" className="text-accent-violet hover:text-accent-violet/80 font-medium">
            Accedi
          </Link>
        </p>
      </div>
    </div>
  );
}
