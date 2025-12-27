'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { getAvatarUrl } from '@/lib/discord';
import LoginModal from '@/components/LoginModal';
import Image from 'next/image';

export default function Navbar() {
  const { user, isAuthenticated, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);

  return (
    <nav className="fixed top-0 left-0 right-0 z-50" style={{
      backdropFilter: 'blur(8px)',
      background: 'rgba(13, 11, 20, 0.85)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.05)'
    }}>
      <div className="container mx-auto px-4 py-3 md:py-4">
        <div className="flex items-center justify-between">
          {/* Logo with glow on hover */}
          <Link href="/" className="flex items-center space-x-2 md:space-x-3 group relative">
            <div className="absolute inset-0 blur-md bg-[#8f60ff] opacity-0 group-hover:opacity-30 transition-opacity rounded-full"></div>
            <Image
              src="/logo.png"
              alt="Afroo Exchange"
              width={32}
              height={32}
              className="transform group-hover:scale-110 transition-transform relative z-10 md:w-10 md:h-10"
            />
            <span className="text-lg md:text-xl font-bold gradient-text relative z-10">Afroo Exchange</span>
          </Link>

          {/* Mobile Menu Button */}
          <button
            className="md:hidden text-white p-2"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {mobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>

          {/* Desktop Navigation Links */}
          <div className="hidden md:flex items-center space-x-4 lg:space-x-6">
            <Link href="/" className="nav-link text-sm lg:text-base" style={{ color: '#a9a4be' }}>
              Home
            </Link>
            <Link href="/wallet" className="nav-link text-sm lg:text-base" style={{ color: '#a9a4be' }}>
              Wallet
            </Link>
            <Link href="/swap" className="nav-link text-sm lg:text-base" style={{ color: '#a9a4be' }}>
              Swap
            </Link>
            <Link href="/leaderboard" className="nav-link text-sm lg:text-base" style={{ color: '#a9a4be' }}>
              Leaderboard
            </Link>
            <Link href="/tos" className="nav-link text-sm lg:text-base" style={{ color: '#a9a4be' }}>
              TOS
            </Link>
            <a
              href="https://discord.gg/afrooexch"
              target="_blank"
              rel="noopener noreferrer"
              className="nav-link text-sm lg:text-base flex items-center gap-1"
              style={{ color: '#a9a4be' }}
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z"/>
              </svg>
              Discord
            </a>
          </div>

          {/* Desktop Auth Section */}
          <div className="hidden md:flex items-center space-x-3 lg:space-x-4">
            {isAuthenticated && user ? (
              <>
                <Link href="/dashboard" className="btn-ghost text-sm px-4 py-2 cursor-pointer">
                  Dashboard
                </Link>
                <div className="flex items-center space-x-2 card px-3 py-2 pointer-events-none">
                  <Image
                    src={getAvatarUrl(user, 64)}
                    alt={user.username}
                    width={28}
                    height={28}
                    className="rounded-full"
                  />
                  <span className="text-xs lg:text-sm font-medium text-white">
                    {user.username}
                  </span>
                </div>
                <button onClick={logout} className="btn-secondary text-xs lg:text-sm px-4 py-2 cursor-pointer active:scale-95">
                  Logout
                </button>
              </>
            ) : (
              <button onClick={() => setShowLoginModal(true)} className="btn-primary text-sm px-4 lg:px-6 py-2 cursor-pointer active:scale-95">
                Login with Discord
              </button>
            )}
          </div>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden mt-4 pb-4 border-t" style={{ borderColor: 'rgba(255, 255, 255, 0.05)' }}>
            <div className="flex flex-col space-y-3 pt-4">
              <Link
                href="/"
                className="nav-link px-2 py-2 text-base"
                style={{ color: '#a9a4be' }}
                onClick={() => setMobileMenuOpen(false)}
              >
                Home
              </Link>
              <Link
                href="/wallet"
                className="nav-link px-2 py-2 text-base"
                style={{ color: '#a9a4be' }}
                onClick={() => setMobileMenuOpen(false)}
              >
                Wallet
              </Link>
              <Link
                href="/swap"
                className="nav-link px-2 py-2 text-base"
                style={{ color: '#a9a4be' }}
                onClick={() => setMobileMenuOpen(false)}
              >
                Swap
              </Link>
              <Link
                href="/leaderboard"
                className="nav-link px-2 py-2 text-base"
                style={{ color: '#a9a4be' }}
                onClick={() => setMobileMenuOpen(false)}
              >
                Leaderboard
              </Link>
              <Link
                href="/tos"
                className="nav-link px-2 py-2 text-base"
                style={{ color: '#a9a4be' }}
                onClick={() => setMobileMenuOpen(false)}
              >
                TOS
              </Link>
              <a
                href="https://discord.gg/afrooexch"
                target="_blank"
                rel="noopener noreferrer"
                className="nav-link px-2 py-2 text-base flex items-center gap-2"
                style={{ color: '#a9a4be' }}
                onClick={() => setMobileMenuOpen(false)}
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z"/>
                </svg>
                Discord
              </a>

              {/* Mobile Auth */}
              <div className="pt-2 border-t" style={{ borderColor: 'rgba(255, 255, 255, 0.05)' }}>
                {isAuthenticated && user ? (
                  <>
                    <Link
                      href="/dashboard"
                      className="btn-ghost text-sm w-full mb-2 cursor-pointer block text-center"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      Dashboard
                    </Link>
                    <div className="flex items-center space-x-2 card px-3 py-2 mb-2 pointer-events-none">
                      <Image
                        src={getAvatarUrl(user, 64)}
                        alt={user.username}
                        width={28}
                        height={28}
                        className="rounded-full"
                      />
                      <span className="text-sm font-medium text-white">
                        {user.username}
                      </span>
                    </div>
                    <button
                      onClick={() => {
                        logout();
                        setMobileMenuOpen(false);
                      }}
                      className="btn-secondary text-sm w-full cursor-pointer active:scale-95"
                    >
                      Logout
                    </button>
                  </>
                ) : (
                  <button
                    onClick={() => {
                      setShowLoginModal(true);
                      setMobileMenuOpen(false);
                    }}
                    className="btn-primary text-sm w-full cursor-pointer active:scale-95"
                  >
                    Login with Discord
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Login Modal */}
      <LoginModal isOpen={showLoginModal} onClose={() => setShowLoginModal(false)} />

      <style jsx>{`
        .nav-link {
          position: relative;
          display: inline-block;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          cursor: pointer;
        }

        .nav-link:hover {
          color: white !important;
          filter: drop-shadow(0 0 8px rgba(143, 96, 255, 0.4));
        }

        .nav-link::after {
          content: '';
          position: absolute;
          bottom: -4px;
          left: 0;
          width: 0;
          height: 2px;
          background: linear-gradient(90deg, #bfa3ff, #6d35ff);
          transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: 0 0 12px rgba(143, 96, 255, 0.6);
          pointer-events: none;
        }

        .nav-link:hover::after {
          width: 100%;
        }
      `}</style>
    </nav>
  );
}
