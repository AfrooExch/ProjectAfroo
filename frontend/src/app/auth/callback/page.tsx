'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

// Force dynamic rendering to prevent pre-rendering errors
export const dynamic = 'force-dynamic';

function AuthCallbackContent() {
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const { handleDiscordCallback } = useAuth();

  useEffect(() => {
    const code = searchParams.get('code');
    const errorParam = searchParams.get('error');

    // Check if this is opened in a popup window
    const isPopup = window.opener && !window.opener.closed;

    if (errorParam) {
      setError('Authentication was cancelled or failed');
      if (isPopup) {
        setTimeout(() => window.close(), 2000);
      } else {
        setTimeout(() => router.push('/'), 3000);
      }
      return;
    }

    if (!code) {
      setError('No authorization code received');
      if (isPopup) {
        setTimeout(() => window.close(), 2000);
      } else {
        setTimeout(() => router.push('/'), 3000);
      }
      return;
    }

    if (isPopup) {
      // Send code to parent window via postMessage
      try {
        window.opener.postMessage(
          { type: 'DISCORD_AUTH_CODE', code },
          window.location.origin
        );
        setSuccess(true);
        setTimeout(() => window.close(), 1500);
      } catch (err) {
        console.error('Failed to send message to parent:', err);
        setError('Failed to communicate with parent window');
      }
    } else {
      // Normal flow (not in popup)
      handleDiscordCallback(code)
        .then(() => {
          router.push('/wallet');
        })
        .catch((err) => {
          console.error('Auth callback error:', err);
          setError('Authentication failed. Please try again.');
          setTimeout(() => router.push('/'), 3000);
        });
    }
  }, [searchParams, handleDiscordCallback, router]);

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(to bottom, #000000, #0a0014)' }}>
        <div className="text-center p-8 rounded-2xl" style={{
          background: 'rgba(168, 131, 255, 0.03)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(168, 131, 255, 0.1)'
        }}>
          <div className="text-6xl mb-4">✅</div>
          <h1 className="text-2xl font-bold text-white mb-2">Success!</h1>
          <p style={{ color: '#9693a8' }}>Completing your login...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(to bottom, #000000, #0a0014)' }}>
        <div className="text-center p-8 rounded-2xl" style={{
          background: 'rgba(168, 131, 255, 0.03)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(168, 131, 255, 0.1)'
        }}>
          <div className="text-6xl mb-4">❌</div>
          <h1 className="text-2xl font-bold text-white mb-2">Authentication Failed</h1>
          <p style={{ color: '#9693a8' }} className="mb-4">{error}</p>
          <p style={{ color: '#9693a8' }} className="text-sm">This window will close automatically...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(to bottom, #000000, #0a0014)' }}>
      <div className="text-center p-8 rounded-2xl" style={{
        background: 'rgba(168, 131, 255, 0.03)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(168, 131, 255, 0.1)'
      }}>
        <div className="relative w-16 h-16 mx-auto mb-6">
          <div className="absolute inset-0 rounded-full border-4 border-t-transparent animate-spin" style={{ borderColor: '#a883ff transparent transparent transparent' }}></div>
        </div>
        <h1 className="text-2xl font-bold text-white mb-2">Authenticating...</h1>
        <p style={{ color: '#9693a8' }}>Please wait while we complete your login</p>
      </div>
    </div>
  );
}

export default function AuthCallback() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(to bottom, #000000, #0a0014)' }}>
        <div className="relative w-16 h-16">
          <div className="absolute inset-0 rounded-full border-4 border-t-transparent animate-spin" style={{ borderColor: '#a883ff transparent transparent transparent' }}></div>
        </div>
      </div>
    }>
      <AuthCallbackContent />
    </Suspense>
  );
}
