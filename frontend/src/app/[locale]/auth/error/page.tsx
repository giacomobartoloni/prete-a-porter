'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { AlertCircle, ArrowLeft, RefreshCw, Loader2 } from 'lucide-react';
import Link from 'next/link';

function ErrorContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const errorParam = searchParams.get('error');
    
    const errorMessages: Record<string, string> = {
      Configuration: 'There is a problem with the server configuration.',
      AccessDenied: 'You do not have access to this resource.',
      Verification: 'The verification token has expired or has already been used.',
      Default: 'An unexpected error occurred during authentication.',
      OAuthSignin: 'Error in the OAuth sign-in process.',
      OAuthCallback: 'Error in the OAuth callback process.',
      OAuthCreateAccount: 'Could not create OAuth account.',
      EmailCreateAccount: 'Could not create email account.',
      Callback: 'Error in the OAuth callback handler.',
      OAuthAccountNotLinked: 'This email is already associated with another account.',
      EmailSignin: 'Could not send the email for sign-in.',
      CredentialsSignin: 'Invalid email or password. Please try again.',
      SessionRequired: 'Please sign in to access this page.',
    };

    setError(errorMessages[errorParam || 'Default'] || errorMessages.Default);
  }, [searchParams]);

  return (
    <>
      <p className="text-text-secondary text-center mb-6">
        {error || 'An error occurred during authentication.'}
      </p>

      <div className="space-y-3">
        <button
          onClick={() => router.push('/auth/login')}
          className="w-full flex items-center justify-center gap-2 bg-accent-blue text-white py-2.5 px-4 rounded-lg hover:bg-accent-blue/90 focus:outline-none focus:ring-2 focus:ring-accent-blue focus:ring-offset-2 transition-colors font-medium"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back to Sign In</span>
        </button>
        
        <button
          onClick={() => router.refresh()}
          className="w-full flex items-center justify-center gap-2 bg-bg-overlay text-text-secondary py-2.5 px-4 rounded-lg hover:bg-bg-overlay/80 focus:outline-none focus:ring-2 focus:ring-border focus:ring-offset-2 transition-colors font-medium"
        >
          <RefreshCw className="w-5 h-5" />
          <span>Try Again</span>
        </button>
      </div>
    </>
  );
}

function ErrorFallback() {
  return (
    <>
      <div className="flex items-center justify-center py-4">
        <Loader2 className="w-6 h-6 animate-spin text-text-tertiary" />
      </div>
      <div className="space-y-3">
        <Link
          href="/auth/login"
          className="w-full flex items-center justify-center gap-2 bg-accent-blue text-white py-2.5 px-4 rounded-lg hover:bg-accent-blue/90 focus:outline-none focus:ring-2 focus:ring-accent-blue focus:ring-offset-2 transition-colors font-medium"
        >
          <ArrowLeft className="w-5 h-5" />
          <span>Back to Sign In</span>
        </Link>
      </div>
    </>
  );
}

export default function ErrorPage() {
  return (
    <div className="min-h-screen bg-bg-canvas flex flex-col items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        <div className="bg-bg-card rounded-xl border border-border p-6">
          <div className="flex items-center justify-center w-12 h-12 mx-auto mb-4 bg-danger/10 rounded-full">
            <AlertCircle className="w-6 h-6 text-danger" />
          </div>
          
          <h1 className="text-xl font-semibold text-text-primary text-center mb-2">
            Authentication Error
          </h1>
          
          <Suspense fallback={<ErrorFallback />}>
            <ErrorContent />
          </Suspense>
        </div>

        <p className="text-center text-sm text-text-tertiary mt-6">
          Need help?{' '}
          <Link href="/" className="text-accent-blue hover:text-accent-blue/80 font-medium">
            Go back home
          </Link>
        </p>
      </div>
    </div>
  );
}
