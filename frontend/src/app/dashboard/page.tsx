'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import LoginModal from '@/components/LoginModal';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/lib/api';
import toast, { Toaster } from 'react-hot-toast';

interface Wallet {
  currency: string;
  address: string;
  available: string;
  locked: string;
  pending: string;
  total: string;
  usd_value: string | number | null;
}

interface ComprehensiveStats {
  client_total_exchanges: number;
  client_completed_exchanges: number;
  client_cancelled_exchanges: number;
  client_exchange_volume_usd: number;
  exchanger_total_completed: number;
  exchanger_total_claimed: number;
  exchanger_total_fees_paid_usd: number;
  exchanger_total_profit_usd: number;
  exchanger_exchange_volume_usd: number;
  exchanger_tickets_completed: number;
  swap_total_made: number;
  swap_total_completed: number;
  swap_total_failed: number;
  swap_total_volume_usd: number;
  automm_total_created: number;
  automm_total_completed: number;
  automm_total_volume_usd: number;
  wallet_total_deposited_usd: number;
  wallet_total_withdrawn_usd: number;
  reputation_score: number;
  roles: string[];
}

export default function DashboardPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [stats, setStats] = useState<ComprehensiveStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'stats' | 'wallets' | 'tickets' | 'transcripts'>('overview');
  const [tickets, setTickets] = useState<any[]>([]);
  const [transcripts, setTranscripts] = useState<any[]>([]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      setLoading(false);
      return;
    }

    if (isAuthenticated && user?.id) {
      loadDashboardData();
    }
  }, [isAuthenticated, isLoading, user?.id]);

  const loadDashboardData = async () => {
    if (!user?.id) return;

    try {
      const [statsData, walletsData, ticketsData, transcriptsData] = await Promise.all([
        api.getUserStats(user.id),
        api.getWallets(),
        api.getMyTickets().catch(() => ({ tickets: [] })),
        api.getUserTranscripts(user.id, 10).catch(() => ({ transcripts: [] }))
      ]);

      setStats(statsData as ComprehensiveStats);
      const balances = (walletsData as any).data?.balances || (walletsData as any).balances || [];
      setWallets(balances);
      const ticketsList = (ticketsData as any).tickets || [];
      setTickets(ticketsList.slice(0, 5)); // Show only 5 recent tickets
      const transcriptsList = (transcriptsData as any).transcripts || [];
      setTranscripts(transcriptsList);
    } catch (error) {
      console.error('Failed to load dashboard:', error);
      toast.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  // Calculate aggregate stats
  const totalBalance = wallets.reduce((sum, w) => {
    const usdValue = typeof w.usd_value === 'number'
      ? w.usd_value
      : parseFloat(w.usd_value || '0');
    return sum + usdValue;
  }, 0);

  const totalVolume = (stats?.client_exchange_volume_usd || 0) +
                     (stats?.exchanger_exchange_volume_usd || 0) +
                     (stats?.swap_total_volume_usd || 0) +
                     (stats?.automm_total_volume_usd || 0);

  const totalExchanges = (stats?.client_total_exchanges || 0) +
                        (stats?.exchanger_total_completed || 0);

  const totalSwaps = stats?.swap_total_made || 0;

  const successRate = totalExchanges > 0
    ? (((stats?.client_completed_exchanges || 0) + (stats?.exchanger_total_completed || 0)) / totalExchanges * 100)
    : 0;

  // Loading state
  if (isLoading || loading) {
    return (
      <div className="min-h-screen relative" style={{ background: 'radial-gradient(circle at top right, #1c1528 0%, #0d0b14 70%)' }}>
        <Navbar />
        <Toaster position="top-right" />
        <div className="flex items-center justify-center min-h-[80vh]">
          <div className="relative">
            <div className="w-16 h-16 border-4 border-[#6d35ff]/20 border-t-[#a883ff] rounded-full animate-spin"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen relative" style={{ background: 'radial-gradient(circle at top right, #1c1528 0%, #0d0b14 70%)' }}>
      <Navbar />
      <Toaster position="top-right" />

      {/* Login Modal Overlay */}
      {!isAuthenticated && (
        <>
          <div className="fixed inset-0 z-40 flex items-center justify-center p-4"
               style={{ background: 'rgba(0, 0, 0, 0.7)', backdropFilter: 'blur(12px)' }}>
            <div className="text-center p-8 rounded-2xl"
                 style={{
                   background: 'rgba(255, 255, 255, 0.05)',
                   border: '1px solid rgba(160, 120, 255, 0.2)',
                   backdropFilter: 'blur(20px)'
                 }}>
              <h2 className="text-2xl font-bold text-white mb-4">Access Dashboard</h2>
              <p className="text-gray-400 mb-6">Please log in to view your dashboard</p>
              <button
                onClick={() => setShowLoginModal(true)}
                className="px-8 py-3 rounded-xl font-semibold text-white transition-all"
                style={{
                  background: 'linear-gradient(135deg, #a883ff, #6d35ff)',
                  boxShadow: '0 4px 16px rgba(168, 131, 255, 0.3)'
                }}
              >
                Login with Discord
              </button>
            </div>
          </div>
          {showLoginModal && <LoginModal isOpen={showLoginModal} onClose={() => setShowLoginModal(false)} />}
        </>
      )}

      <div className="container mx-auto px-4 pt-24 pb-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
            Welcome back, <span className="bg-gradient-to-r from-[#d7c6ff] via-[#a883ff] to-[#6d35ff] bg-clip-text text-transparent">{user?.username}</span>
          </h1>
          <div className="flex flex-wrap items-center gap-4 mt-3">
            <p className="text-sm md:text-base" style={{ color: '#b0adc0' }}>
              Discord ID: {user?.id}
            </p>
            {stats && stats.roles.length > 0 && (
              <div className="flex gap-2 flex-wrap">
                {stats.roles.map((role, idx) => (
                  <span key={idx} className="px-3 py-1 rounded-full text-xs font-semibold"
                        style={{
                          background: 'rgba(168, 131, 255, 0.15)',
                          border: '1px solid rgba(168, 131, 255, 0.3)',
                          color: '#a883ff'
                        }}>
                    {role}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-2 mb-8 overflow-x-auto pb-2">
          {[
            { id: 'overview', name: 'Overview' },
            { id: 'stats', name: 'Statistics' },
            { id: 'wallets', name: 'Wallets' },
            { id: 'tickets', name: 'Recent Tickets' },
            { id: 'transcripts', name: 'Transcripts' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className="px-6 py-3 rounded-xl font-semibold transition-all whitespace-nowrap"
              style={{
                background: activeTab === tab.id
                  ? 'linear-gradient(135deg, rgba(168, 131, 255, 0.2), rgba(109, 53, 255, 0.2))'
                  : 'rgba(255, 255, 255, 0.03)',
                border: activeTab === tab.id
                  ? '1px solid rgba(160, 120, 255, 0.4)'
                  : '1px solid rgba(160, 120, 255, 0.15)',
                color: activeTab === tab.id ? 'white' : '#b0adc0',
              }}
            >
              {tab.name}
            </button>
          ))}
        </div>

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-8">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
              <div className="card" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
                <div className="text-sm mb-2" style={{ color: '#b0adc0' }}>Total Balance</div>
                <div className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-[#d7c6ff] via-[#a883ff] to-[#6d35ff] bg-clip-text text-transparent">
                  ${totalBalance.toFixed(2)}
                </div>
                <div className="text-xs mt-1" style={{ color: '#9693a8' }}>
                  Across {wallets.length} wallets
                </div>
              </div>

              <div className="card" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
                <div className="text-sm mb-2" style={{ color: '#b0adc0' }}>Total Volume</div>
                <div className="text-2xl md:text-3xl font-bold text-white">
                  ${totalVolume.toFixed(2)}
                </div>
                <div className="text-xs mt-1" style={{ color: '#9693a8' }}>
                  All-time trading
                </div>
              </div>

              <div className="card" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
                <div className="text-sm mb-2" style={{ color: '#b0adc0' }}>Total Trades</div>
                <div className="text-2xl md:text-3xl font-bold text-white">
                  {totalExchanges + totalSwaps}
                </div>
                <div className="text-xs mt-1" style={{ color: '#9693a8' }}>
                  {totalExchanges} P2P • {totalSwaps} Swaps
                </div>
              </div>

              <div className="card" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
                <div className="text-sm mb-2" style={{ color: '#b0adc0' }}>Success Rate</div>
                <div className="text-2xl md:text-3xl font-bold" style={{ color: '#2ed573' }}>
                  {successRate.toFixed(0)}%
                </div>
                <div className="text-xs mt-1" style={{ color: '#9693a8' }}>
                  Completed trades
                </div>
              </div>
            </div>

            {/* Activity Breakdown */}
            {stats && (
              <div className="grid md:grid-cols-2 gap-6">
                <div className="card" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
                  <h3 className="text-lg font-semibold text-white mb-4">Exchange Activity</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span style={{ color: '#b0adc0' }}>Total</span>
                      <span className="font-semibold text-white">{stats.client_total_exchanges}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span style={{ color: '#b0adc0' }}>Completed</span>
                      <span className="font-semibold text-white">{stats.client_completed_exchanges}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span style={{ color: '#b0adc0' }}>Volume</span>
                      <span className="font-semibold text-white">${stats.client_exchange_volume_usd.toFixed(2)}</span>
                    </div>
                  </div>
                </div>

                <div className="card" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
                  <h3 className="text-lg font-semibold text-white mb-4">Exchanger Stats</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span style={{ color: '#b0adc0' }}>Completed</span>
                      <span className="font-semibold text-white">{stats.exchanger_total_completed}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span style={{ color: '#b0adc0' }}>Volume</span>
                      <span className="font-semibold text-white">${stats.exchanger_exchange_volume_usd.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span style={{ color: '#b0adc0' }}>Profit</span>
                      <span className="font-semibold text-white">${stats.exchanger_total_profit_usd.toFixed(2)}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Statistics Tab */}
        {activeTab === 'stats' && stats && (
          <div className="space-y-6">
            {/* Swap Stats */}
            <div className="card" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
              <h3 className="text-xl font-semibold text-white mb-4">Swap Statistics</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-sm" style={{ color: '#b0adc0' }}>Total Made</div>
                  <div className="text-2xl font-bold text-white mt-1">{stats.swap_total_made}</div>
                </div>
                <div>
                  <div className="text-sm" style={{ color: '#b0adc0' }}>Completed</div>
                  <div className="text-2xl font-bold text-white mt-1">{stats.swap_total_completed}</div>
                </div>
                <div>
                  <div className="text-sm" style={{ color: '#b0adc0' }}>Failed</div>
                  <div className="text-2xl font-bold text-white mt-1">{stats.swap_total_failed}</div>
                </div>
                <div>
                  <div className="text-sm" style={{ color: '#b0adc0' }}>Volume</div>
                  <div className="text-2xl font-bold text-white mt-1">${stats.swap_total_volume_usd.toFixed(2)}</div>
                </div>
              </div>
            </div>

            {/* AutoMM Stats */}
            <div className="card" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
              <h3 className="text-xl font-semibold text-white mb-4">AutoMM Statistics</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <div>
                  <div className="text-sm" style={{ color: '#b0adc0' }}>Created</div>
                  <div className="text-2xl font-bold text-white mt-1">{stats.automm_total_created}</div>
                </div>
                <div>
                  <div className="text-sm" style={{ color: '#b0adc0' }}>Completed</div>
                  <div className="text-2xl font-bold text-white mt-1">{stats.automm_total_completed}</div>
                </div>
                <div>
                  <div className="text-sm" style={{ color: '#b0adc0' }}>Volume</div>
                  <div className="text-2xl font-bold text-white mt-1">${stats.automm_total_volume_usd.toFixed(2)}</div>
                </div>
              </div>
            </div>

            {/* Wallet Stats */}
            <div className="card" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
              <h3 className="text-xl font-semibold text-white mb-4">Wallet Activity</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm" style={{ color: '#b0adc0' }}>Total Deposited</div>
                  <div className="text-2xl font-bold text-white mt-1">${stats.wallet_total_deposited_usd.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-sm" style={{ color: '#b0adc0' }}>Total Withdrawn</div>
                  <div className="text-2xl font-bold text-white mt-1">${stats.wallet_total_withdrawn_usd.toFixed(2)}</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Wallets Tab */}
        {activeTab === 'wallets' && (
          <div className="space-y-4">
            {wallets.length === 0 ? (
              <div className="card text-center py-12" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
                <p style={{ color: '#b0adc0' }}>No wallets found</p>
              </div>
            ) : (
              wallets.map((wallet) => {
                const usdValue = typeof wallet.usd_value === 'number'
                  ? wallet.usd_value
                  : parseFloat(wallet.usd_value || '0');

                return (
                  <div key={wallet.currency} className="card" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
                    <div className="flex justify-between items-center">
                      <div>
                        <h3 className="text-lg font-semibold text-white">{wallet.currency}</h3>
                        <p className="text-sm" style={{ color: '#b0adc0' }}>{wallet.total} {wallet.currency}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-bold text-white">${usdValue.toFixed(2)}</p>
                        <p className="text-xs" style={{ color: '#9693a8' }}>
                          Available: {wallet.available}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* Tickets Tab */}
        {activeTab === 'tickets' && (
          <div className="space-y-4">
            {tickets.length === 0 ? (
              <div className="card text-center py-12" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
                <p style={{ color: '#b0adc0' }}>No recent tickets</p>
              </div>
            ) : (
              tickets.map((ticket) => {
                const statusColors: Record<string, string> = {
                  'pending': '#ffa500',
                  'accepted': '#2ed573',
                  'completed': '#2ed573',
                  'cancelled': '#ff4757',
                  'disputed': '#ff4757',
                };
                const statusColor = statusColors[ticket.status] || '#b0adc0';

                return (
                  <div key={ticket.id} className="card" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <h3 className="text-lg font-semibold text-white">
                          {ticket.from_currency} → {ticket.to_currency}
                        </h3>
                        <p className="text-sm" style={{ color: '#b0adc0' }}>
                          Ticket #{ticket.id?.slice(0, 8)}
                        </p>
                      </div>
                      <span className="px-3 py-1 rounded-full text-xs font-semibold"
                            style={{
                              background: `${statusColor}20`,
                              border: `1px solid ${statusColor}40`,
                              color: statusColor
                            }}>
                        {ticket.status}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <div className="text-xs" style={{ color: '#9693a8' }}>Amount</div>
                        <div className="text-sm font-semibold text-white">{ticket.amount} {ticket.from_currency}</div>
                      </div>
                      <div>
                        <div className="text-xs" style={{ color: '#9693a8' }}>USD Value</div>
                        <div className="text-sm font-semibold text-white">${ticket.amount_usd?.toFixed(2) || '0.00'}</div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* Transcripts Tab */}
        {activeTab === 'transcripts' && (
          <div className="space-y-4">
            {transcripts.length === 0 ? (
              <div className="card text-center py-12" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
                <p style={{ color: '#b0adc0' }}>No transcripts available</p>
              </div>
            ) : (
              transcripts.map((transcript) => {
                // Format date
                const date = new Date(transcript.generated_at);
                const formattedDate = date.toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit'
                });

                // Type badge colors
                const typeColors: Record<string, string> = {
                  'ticket': '#6d35ff',
                  'swap': '#2ed573',
                  'automm': '#ffa500',
                  'application': '#ff4757',
                  'support': '#a883ff',
                };
                const typeColor = typeColors[transcript.ticket_type] || '#b0adc0';

                return (
                  <div key={transcript.ticket_id} className="card" style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(160, 120, 255, 0.15)', borderRadius: '16px', padding: '24px' }}>
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <h3 className="text-lg font-semibold text-white mb-1">
                          {transcript.ticket_type.charAt(0).toUpperCase() + transcript.ticket_type.slice(1)} Transcript
                        </h3>
                        <p className="text-sm" style={{ color: '#b0adc0' }}>
                          ID: {transcript.ticket_id.slice(0, 12)}...
                        </p>
                      </div>
                      <span className="px-3 py-1 rounded-full text-xs font-semibold"
                            style={{
                              background: `${typeColor}20`,
                              border: `1px solid ${typeColor}40`,
                              color: typeColor
                            }}>
                        {transcript.ticket_type}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
                      <div>
                        <div className="text-xs" style={{ color: '#9693a8' }}>Messages</div>
                        <div className="text-sm font-semibold text-white">{transcript.message_count}</div>
                      </div>
                      <div>
                        <div className="text-xs" style={{ color: '#9693a8' }}>Generated</div>
                        <div className="text-sm font-semibold text-white">{formattedDate}</div>
                      </div>
                      <div>
                        <div className="text-xs" style={{ color: '#9693a8' }}>Views</div>
                        <div className="text-sm font-semibold text-white">{transcript.view_count || 0}</div>
                      </div>
                    </div>

                    <a
                      href={transcript.public_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-block px-6 py-2 rounded-lg font-semibold transition-all"
                      style={{
                        background: 'linear-gradient(135deg, #a883ff, #6d35ff)',
                        color: 'white',
                        textDecoration: 'none'
                      }}
                    >
                      View Transcript →
                    </a>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>
    </div>
  );
}
