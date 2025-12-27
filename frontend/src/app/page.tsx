'use client';

import { useState } from 'react';
import Link from 'next/link';
import Navbar from '@/components/Navbar';
import LoadingAnimation from '@/components/LoadingAnimation';
import LoginModal from '@/components/LoginModal';
import { useAuth } from '@/contexts/AuthContext';

export default function HomePage() {
  const { isAuthenticated } = useAuth();
  const [showContent, setShowContent] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);

  return (
    <>
      {!showContent && <LoadingAnimation onComplete={() => setShowContent(true)} />}

      <div className={`min-h-screen transition-opacity duration-700 ${showContent ? 'opacity-100' : 'opacity-0'}`} style={{ scrollBehavior: 'smooth' }}>
        <Navbar />

        {/* Hero Section - Ultra Clean & Modern */}
        <section className="relative min-h-screen flex items-center justify-center px-6 overflow-hidden pt-32">
          {/* Layered Background Effects */}
          <div className="absolute inset-0 pointer-events-none" style={{
            background: 'radial-gradient(circle at 30% 10%, rgba(135, 90, 255, 0.12) 0%, transparent 60%)'
          }}></div>
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#1b1326]/30 to-[#0c0a12] pointer-events-none"></div>

          {/* Ultra Subtle Atmospheric Triangles */}
          <div className="absolute top-20 right-10 animate-pulse-slow" style={{
            width: 0, height: 0, borderStyle: 'solid',
            borderWidth: '0 90px 150px 90px',
            borderColor: 'transparent transparent #c8b0ff transparent',
            opacity: 0.04, filter: 'blur(20px)', transform: 'scale(0.7)',
            animationDuration: '5s'
          }}></div>
          <div className="absolute bottom-40 left-10 animate-pulse-slow" style={{
            width: 0, height: 0, borderStyle: 'solid',
            borderWidth: '112px 75px 0 75px',
            borderColor: '#c8b0ff transparent transparent transparent',
            opacity: 0.04, filter: 'blur(20px)', transform: 'scale(0.7)',
            animationDelay: '2s', animationDuration: '5s'
          }}></div>

          {/* Soft Purple Fog */}
          <div className="absolute inset-0 -z-10 pointer-events-none" style={{
            background: 'radial-gradient(circle at center, rgba(90, 58, 196, 0.25), transparent 75%)'
          }}></div>

          <div className="container mx-auto text-center relative z-10 max-w-5xl">
            {/* Main Headline */}
            <div className="space-y-8 animate-fade-in">
              <h1 className="text-6xl sm:text-7xl md:text-8xl lg:text-9xl font-bold leading-[1.1] tracking-tight">
                <span className="inline-block bg-gradient-to-r from-[#d7c6ff] via-[#a883ff] to-[#6d35ff] bg-clip-text text-transparent animate-slide-up" style={{
                  textShadow: '0 0 10px rgba(160, 110, 255, 0.3), 0 0 22px rgba(130, 80, 255, 0.18)',
                  WebkitTextStroke: '0.5px rgba(215, 198, 255, 0.1)'
                }}>
                  Afroo Exchange
                </span>
              </h1>

              {/* Refined Tagline */}
              <p className="text-xl sm:text-2xl md:text-3xl font-light tracking-wide animate-slide-up" style={{
                color: '#d0cde0',
                animationDelay: '0.15s',
                letterSpacing: '0.02em',
                textShadow: '0 0 8px rgba(140, 95, 255, 0.2)'
              }}>
                Escrow Secure · Trusted for 2+ years
              </p>

              {/* CTA Buttons - Premium Design */}
              <div className="flex flex-col sm:flex-row items-center justify-center gap-5 pt-6 animate-slide-up" style={{ animationDelay: '0.25s' }}>
                {isAuthenticated ? (
                  <>
                    <Link href="/dashboard" className="premium-btn-primary">
                      Dashboard
                    </Link>
                    <Link href="/swap" className="premium-btn-secondary">
                      Start Swap
                    </Link>
                  </>
                ) : (
                  <>
                    <button onClick={() => setShowLoginModal(true)} className="premium-btn-primary">
                      Login with Discord
                    </button>
                    <Link href="/leaderboard" className="premium-btn-secondary">
                      View Leaderboard
                    </Link>
                  </>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* Stats Section - Refined & Modern */}
        <section className="py-24 md:py-32 px-6 relative">
          {/* Elegant Separator */}
          <div className="absolute top-0 left-0 right-0 h-[1px]" style={{
            background: 'linear-gradient(90deg, transparent, rgba(160, 120, 255, 0.3), transparent)'
          }}></div>

          <div className="container mx-auto max-w-7xl">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 md:gap-8">
              {[
                { value: '$1M+', label: 'Exchanged', delay: '0s' },
                { value: '800+', label: 'Customers', delay: '0.1s' },
                { value: '100+', label: 'Cryptocurrencies', delay: '0.2s' },
                { value: '24/7', label: 'Support', delay: '0.3s' }
              ].map((stat, index) => (
                <div
                  key={index}
                  className="premium-stat-card"
                  style={{ animationDelay: stat.delay }}
                >
                  <div className="text-4xl md:text-6xl font-bold mb-3 bg-gradient-to-r from-[#d7c6ff] via-[#a883ff] to-[#6d35ff] bg-clip-text text-transparent">
                    {stat.value}
                  </div>
                  <div className="text-sm md:text-base font-medium tracking-wide" style={{ color: '#b0adc0' }}>
                    {stat.label}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Footer - Minimalist */}
        <footer className="py-12 md:py-16 px-6 border-t" style={{ borderColor: 'rgba(160, 120, 255, 0.08)' }}>
          <div className="container mx-auto text-center max-w-4xl">
            <p className="text-sm md:text-base font-light tracking-wide" style={{ color: '#9693a8' }}>
              &copy; 2025 Afroo Exchange. All rights reserved.
            </p>
          </div>
        </footer>
      </div>

      <style jsx>{`
        /* Premium Primary Button */
        .premium-btn-primary {
          position: relative;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 1.125rem 3rem;
          font-size: 1.125rem;
          font-weight: 600;
          color: white;
          background: linear-gradient(135deg, #d7c6ff, #a883ff, #6d35ff);
          border-radius: 0.875rem;
          transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: 0 0 20px rgba(150, 95, 255, 0.3), 0 8px 24px rgba(0, 0, 0, 0.15);
          overflow: hidden;
          letter-spacing: 0.02em;
        }

        .premium-btn-primary:hover {
          transform: translateY(-3px);
          box-shadow: 0 0 32px rgba(150, 95, 255, 0.5), 0 12px 32px rgba(0, 0, 0, 0.2);
        }

        .premium-btn-primary:active {
          transform: translateY(-1px);
        }

        /* Premium Secondary Button */
        .premium-btn-secondary {
          position: relative;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 1.125rem 3rem;
          font-size: 1.125rem;
          font-weight: 600;
          color: #e8e6f0;
          background: rgba(255, 255, 255, 0.03);
          backdrop-filter: blur(16px);
          border: 1.5px solid rgba(160, 120, 255, 0.25);
          border-radius: 0.875rem;
          transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          overflow: hidden;
          letter-spacing: 0.02em;
        }

        .premium-btn-secondary:hover {
          background: rgba(255, 255, 255, 0.06);
          border-color: rgba(160, 120, 255, 0.45);
          transform: translateY(-3px);
          box-shadow: 0 0 20px rgba(150, 95, 255, 0.25), 0 12px 32px rgba(0, 0, 0, 0.15);
        }

        .premium-btn-secondary:active {
          transform: translateY(-1px);
        }

        /* Premium Stat Card */
        .premium-stat-card {
          position: relative;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 2.5rem 1.5rem;
          background: rgba(255, 255, 255, 0.02);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(160, 120, 255, 0.12);
          border-radius: 1.5rem;
          transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
          animation: fadeInScale 0.6s ease-out forwards;
          opacity: 0;
          overflow: hidden;
        }

        .premium-stat-card:hover {
          transform: translateY(-8px) scale(1.02);
          border-color: rgba(160, 120, 255, 0.25);
          box-shadow: 0 16px 48px rgba(0, 0, 0, 0.25), 0 0 32px rgba(150, 95, 255, 0.15);
        }

        @keyframes fadeInScale {
          from {
            opacity: 0;
            transform: scale(0.9) translateY(20px);
          }
          to {
            opacity: 1;
            transform: scale(1) translateY(0);
          }
        }

        /* Smooth scroll */
        html {
          scroll-behavior: smooth;
        }

        /* Selection color */
        ::selection {
          background: rgba(168, 131, 255, 0.3);
          color: #ffffff;
        }
      `}</style>

      {/* Login Modal */}
      <LoginModal isOpen={showLoginModal} onClose={() => setShowLoginModal(false)} />
    </>
  );
}
