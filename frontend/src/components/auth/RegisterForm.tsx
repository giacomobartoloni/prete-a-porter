'use client';

import { useState } from 'react';
import { signIn } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Loader2, Mail, Lock, User, AlertCircle } from 'lucide-react';

export default function RegisterForm() {
  const router = useRouter();
  const t = useTranslations('auth.register');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const validateForm = (): boolean => {
    if (!name.trim()) {
      setError(t('name_required'));
      return false;
    }
    if (!email.trim()) {
      setError(t('email_required'));
      return false;
    }
    if (!email.includes('@')) {
      setError(t('invalid_email'));
      return false;
    }
    if (!password) {
      setError(t('password_required'));
      return false;
    }
    if (password.length < 6) {
      setError(t('password_min_length'));
      return false;
    }
    if (password !== confirmPassword) {
      setError(t('passwords_mismatch'));
      return false;
    }
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!validateForm()) return;

    setIsLoading(true);

    try {
      const registerResponse = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim().toLowerCase(),
          password,
        }),
      });

      const registerData = await registerResponse.json();

      if (!registerResponse.ok) {
        setError(registerData.error || t('registration_failed'));
        setIsLoading(false);
        return;
      }

      const result = await signIn('credentials', {
        email: email.trim().toLowerCase(),
        password,
        redirect: false,
      });

      if (result?.error) {
        setError(t('registration_complete'));
        setIsLoading(false);
        return;
      }

      router.push('/chat');
      router.refresh();
    } catch {
      setError(t('error_retry'));
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="flex items-center gap-2 p-3 bg-danger/10 border border-danger/30 rounded-xl text-danger text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label htmlFor="name" className="block text-sm font-medium text-text-secondary mb-1.5">
            {t('name_label')}
          </label>
          <div className="relative">
            <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-accent-violet" />
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('name_placeholder')}
              disabled={isLoading}
              className="w-full pl-10 pr-4 py-2.5 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-accent-violet/30 focus:border-accent-violet disabled:bg-bg-overlay disabled:cursor-not-allowed text-text-primary transition-all"
            />
          </div>
        </div>

        <div>
          <label htmlFor="email" className="block text-sm font-medium text-text-secondary mb-1.5">
            {t('email_label')}
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-accent-violet" />
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={isLoading}
              className="w-full pl-10 pr-4 py-2.5 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-accent-violet/30 focus:border-accent-violet disabled:bg-bg-overlay disabled:cursor-not-allowed text-text-primary transition-all"
            />
          </div>
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-text-secondary mb-1.5">
            {t('password_label')}
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-accent-violet" />
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('password_placeholder')}
              disabled={isLoading}
              className="w-full pl-10 pr-4 py-2.5 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-accent-violet/30 focus:border-accent-violet disabled:bg-bg-overlay disabled:cursor-not-allowed text-text-primary transition-all"
            />
          </div>
        </div>

        <div>
          <label htmlFor="confirmPassword" className="block text-sm font-medium text-text-secondary mb-1.5">
            {t('confirm_password_label')}
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-accent-violet" />
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder={t('confirm_password_placeholder')}
              disabled={isLoading}
              className="w-full pl-10 pr-4 py-2.5 border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-accent-violet/30 focus:border-accent-violet disabled:bg-bg-overlay disabled:cursor-not-allowed text-text-primary transition-all"
            />
          </div>
        </div>
      </div>

      <button
        type="submit"
        disabled={isLoading}
        className="w-full flex items-center justify-center gap-2 bg-accent-violet text-white py-2.5 px-4 rounded-xl hover:bg-accent-violet/90 focus:outline-none focus:ring-2 focus:ring-accent-violet/50 focus:ring-offset-2 disabled:bg-bg-overlay disabled:text-text-tertiary disabled:cursor-not-allowed transition-all font-medium"
      >
        {isLoading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>{t('loading')}</span>
          </>
        ) : (
          <span>{t('submit')}</span>
        )}
      </button>
    </form>
  );
}
