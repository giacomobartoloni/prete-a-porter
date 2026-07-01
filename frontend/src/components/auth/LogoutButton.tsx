'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { signOut } from 'next-auth/react';
import { Loader2, LogOut } from 'lucide-react';

interface LogoutButtonProps {
  className?: string;
  variant?: 'primary' | 'secondary' | 'ghost';
}

export default function LogoutButton({ className = '', variant = 'ghost' }: LogoutButtonProps) {
  const t = useTranslations('auth.logout');
  const [isLoading, setIsLoading] = useState(false);

  const handleLogout = async () => {
    setIsLoading(true);
    try {
      await signOut({ redirect: false });
      window.location.href = '/auth/login';
    } catch (error) {
      console.error('Logout error:', error);
      setIsLoading(false);
    }
  };

  const baseStyles = 'flex items-center justify-center gap-2 font-medium transition-colors disabled:cursor-not-allowed';

  const variantStyles = {
    primary: 'bg-accent-blue text-white py-2.5 px-4 rounded-lg hover:bg-accent-blue/90 disabled:bg-bg-overlay',
    secondary: 'bg-bg-overlay text-text-secondary py-2.5 px-4 rounded-lg hover:bg-bg-overlay/80 disabled:bg-bg-overlay',
    ghost: 'text-text-tertiary hover:text-text-primary py-2 px-3 rounded-lg hover:bg-bg-overlay disabled:text-text-muted',
  };

  return (
    <button
      onClick={handleLogout}
      disabled={isLoading}
      className={`${baseStyles} ${variantStyles[variant]} ${className}`}
    >
      {isLoading ? (
        <>
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>{t('signing_out')}</span>
        </>
      ) : (
        <>
          <LogOut className="w-5 h-5" />
          <span>{t('button')}</span>
        </>
      )}
    </button>
  );
}