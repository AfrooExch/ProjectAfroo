'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';

export default function LoadingAnimation({ onComplete }: { onComplete: () => void }) {
  const [stage, setStage] = useState<'logo' | 'slide' | 'complete'>('logo');

  useEffect(() => {
    const logoTimer = setTimeout(() => {
      setStage('slide');
    }, 1200);

    const completeTimer = setTimeout(() => {
      setStage('complete');
      onComplete();
    }, 2200);

    return () => {
      clearTimeout(logoTimer);
      clearTimeout(completeTimer);
    };
  }, [onComplete]);

  if (stage === 'complete') return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-hidden">
      {/* Background with purple fog */}
      <div className="absolute inset-0 bg-gradient-to-br from-[#0d0b14] via-[#1c1528] to-[#0d0b14]"></div>
      <div className="absolute inset-0" style={{
        background: 'radial-gradient(circle at 30% 10%, rgba(135, 90, 255, 0.15) 0%, transparent 60%)'
      }}></div>

      <div className="relative flex flex-col items-center gap-8">
        {/* Logo with enhanced glow - always centered */}
        <div className={`relative transition-all duration-1000 ease-out ${
          stage === 'logo' ? 'scale-100 opacity-100' : 'scale-95 opacity-90'
        }`}>
          {/* Multiple layered glows for depth */}
          <div className="absolute inset-0 blur-3xl bg-[#8f60ff] opacity-20 rounded-full animate-pulse" style={{ animationDuration: '3s' }}></div>
          <div className="absolute inset-0 blur-2xl bg-[#a883ff] opacity-15 rounded-full animate-pulse" style={{ animationDuration: '2s', animationDelay: '0.5s' }}></div>
          <div className="absolute inset-0 blur-xl bg-[#d7c6ff] opacity-10 rounded-full animate-pulse" style={{ animationDuration: '2.5s', animationDelay: '1s' }}></div>

          <Image
            src="/logo.png"
            alt="Afroo Exchange"
            width={140}
            height={140}
            className="relative z-10"
            style={{ filter: 'drop-shadow(0 0 20px rgba(150, 95, 255, 0.4)) drop-shadow(0 0 40px rgba(135, 90, 255, 0.2))' }}
            priority
          />
        </div>

        {/* Text that fades in below logo with smoother animation */}
        <div className={`transition-all duration-1000 ease-out ${
          stage === 'slide' ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'
        }`}>
          <h1 className="text-5xl md:text-6xl font-bold text-center px-4"
              style={{
                background: 'linear-gradient(90deg, #d7c6ff, #a883ff, #6d35ff)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                filter: 'drop-shadow(0 0 8px rgba(150, 95, 255, 0.3))'
              }}>
            Afroo Exchange
          </h1>
        </div>
      </div>
    </div>
  );
}
