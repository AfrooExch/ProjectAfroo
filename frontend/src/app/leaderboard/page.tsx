'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import Navbar from '@/components/Navbar';
import { getAvatarUrl } from '@/lib/discord';

interface LeaderboardEntry {
  rank: number;
  discord_id: string;
  username: string;
  volume_usd?: number;
  tickets_completed?: number;
  profit_usd?: number;
  total_exchanges?: number;
  completed_exchanges?: number;
  total_swaps?: number;
  completed_swaps?: number;
  total_deals?: number;
  completed_deals?: number;
}

type LeaderboardType = 'exchanger' | 'customer' | 'trader' | 'automm';

export default function LeaderboardPage() {
  const [activeTab, setActiveTab] = useState<LeaderboardType>('exchanger');
  const [leaderboardData, setLeaderboardData] = useState<Record<LeaderboardType, LeaderboardEntry[]>>({
    exchanger: [],
    customer: [],
    trader: [],
    automm: []
  });
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState<LeaderboardEntry | null>(null);

  useEffect(() => {
    loadAllLeaderboards();
  }, []);

  const loadAllLeaderboards = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/admin/stats/leaderboards?limit=50`);

      if (!response.ok) {
        throw new Error('Failed to load leaderboards');
      }

      const data = await response.json();

      // Map the response to our leaderboard format with ranks
      const exchangers = (data.top_exchangers || []).map((entry: any, idx: number) => ({
        rank: idx + 1,
        discord_id: entry.discord_id,
        username: entry.username,
        volume_usd: entry.volume_usd,
        tickets_completed: entry.tickets_completed,
        profit_usd: entry.profit_usd
      }));

      const clients = (data.top_clients || []).map((entry: any, idx: number) => ({
        rank: idx + 1,
        discord_id: entry.discord_id,
        username: entry.username,
        volume_usd: entry.volume_usd,
        total_exchanges: entry.total_exchanges,
        completed_exchanges: entry.completed_exchanges
      }));

      const swappers = (data.top_swappers || []).map((entry: any, idx: number) => ({
        rank: idx + 1,
        discord_id: entry.discord_id,
        username: entry.username,
        volume_usd: entry.volume_usd,
        total_swaps: entry.total_swaps,
        completed_swaps: entry.completed_swaps
      }));

      const automm = (data.top_automm || []).map((entry: any, idx: number) => ({
        rank: idx + 1,
        discord_id: entry.discord_id,
        username: entry.username,
        volume_usd: entry.volume_usd,
        total_deals: entry.total_deals,
        completed_deals: entry.completed_deals
      }));

      setLeaderboardData({
        exchanger: exchangers,
        customer: clients,
        trader: swappers,
        automm: automm
      });
    } catch (error) {
      console.error('Failed to load leaderboards:', error);
      setLeaderboardData({
        exchanger: [],
        customer: [],
        trader: [],
        automm: []
      });
    } finally {
      setLoading(false);
    }
  };

  const getRankBadge = (rank: number) => {
    return rank;
  };

  const tabs = [
    {
      id: 'exchanger' as LeaderboardType,
      name: 'Top Exchangers',
      description: 'By completed exchanges'
    },
    {
      id: 'customer' as LeaderboardType,
      name: 'Top Client (Exchanges)',
      description: 'By exchange volume'
    },
    {
      id: 'trader' as LeaderboardType,
      name: 'Top Swapper',
      description: 'By swap volume'
    },
    {
      id: 'automm' as LeaderboardType,
      name: 'Top AutoMM',
      description: 'By AutoMM volume'
    }
  ];

  const getLeaderboardContent = (type: LeaderboardType) => {
    const data = leaderboardData[type];

    const getStatValue = (entry: LeaderboardEntry) => {
      return {
        volume: entry.volume_usd || 0
      };
    };

    if (loading) {
      return (
        <div className="text-center py-20">
          <div className="relative w-16 h-16 mx-auto">
            <div className="w-16 h-16 border-4 border-[#6d35ff]/20 border-t-[#a883ff] rounded-full animate-spin"></div>
            <div className="absolute inset-0 blur-xl bg-[#8f60ff] opacity-30 rounded-full animate-pulse"></div>
          </div>
          <p className="mt-4" style={{ color: '#b0adc0' }}>Loading rankings...</p>
        </div>
      );
    }

    if (data.length === 0) {
      return (
        <div className="text-center py-20">
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl flex items-center justify-center" style={{
            background: 'linear-gradient(135deg, rgba(215, 198, 255, 0.1), rgba(168, 131, 255, 0.1))',
            border: '1px solid rgba(160, 120, 255, 0.2)'
          }}>
            <svg className="w-10 h-10" style={{ color: '#a883ff' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
            </svg>
          </div>
          <h3 className="text-xl font-semibold text-white mb-2">No Rankings Yet</h3>
          <p style={{ color: '#9693a8' }}>Start trading to climb the leaderboard</p>
        </div>
      );
    }

    return (
      <>
        {/* Top 3 Podium */}
        {data.length >= 3 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 max-w-6xl mx-auto">
            {/* 2nd Place */}
            <div className="premium-podium-card order-2 md:order-1" onClick={() => setSelectedUser(data[1])}>
              <div className="text-4xl font-bold mb-3" style={{ color: '#a883ff' }}>2</div>
              <Image
                src={getAvatarUrl(data[1], 80)}
                alt={data[1].username}
                width={64}
                height={64}
                className="rounded-full mx-auto mb-3"
                style={{
                  border: '3px solid rgba(168, 131, 255, 0.4)',
                  boxShadow: '0 0 15px rgba(168, 131, 255, 0.3)'
                }}
              />
              <div className="text-lg font-bold text-white mb-1">{data[1].username}</div>
              <div className="text-base font-semibold" style={{ color: '#14F195' }}>
                ${getStatValue(data[1]).volume.toLocaleString()}
              </div>
            </div>

            {/* 1st Place */}
            <div className="premium-podium-card premium-podium-first order-1 md:order-2" onClick={() => setSelectedUser(data[0])}>
              <div className="text-5xl font-bold mb-4" style={{ color: '#a883ff' }}>1</div>
              <Image
                src={getAvatarUrl(data[0], 96)}
                alt={data[0].username}
                width={80}
                height={80}
                className="rounded-full mx-auto mb-4"
                style={{
                  border: '4px solid rgba(168, 131, 255, 0.6)',
                  boxShadow: '0 0 25px rgba(168, 131, 255, 0.5)'
                }}
              />
              <div className="text-2xl font-bold text-white mb-2">{data[0].username}</div>
              <div className="text-xl font-bold" style={{ color: '#14F195' }}>
                ${getStatValue(data[0]).volume.toLocaleString()}
              </div>
            </div>

            {/* 3rd Place */}
            <div className="premium-podium-card order-3" onClick={() => setSelectedUser(data[2])}>
              <div className="text-4xl font-bold mb-3" style={{ color: '#a883ff' }}>3</div>
              <Image
                src={getAvatarUrl(data[2], 80)}
                alt={data[2].username}
                width={64}
                height={64}
                className="rounded-full mx-auto mb-3"
                style={{
                  border: '3px solid rgba(168, 131, 255, 0.4)',
                  boxShadow: '0 0 15px rgba(168, 131, 255, 0.3)'
                }}
              />
              <div className="text-lg font-bold text-white mb-1">{data[2].username}</div>
              <div className="text-base font-semibold" style={{ color: '#14F195' }}>
                ${getStatValue(data[2]).volume.toLocaleString()}
              </div>
            </div>
          </div>
        )}

        {/* Leaderboard Table */}
        <div className="premium-table-container">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b" style={{ borderColor: 'rgba(160, 120, 255, 0.15)' }}>
                  <th className="px-4 md:px-6 py-4 text-left text-xs md:text-sm font-medium" style={{ color: '#9693a8' }}>Rank</th>
                  <th className="px-4 md:px-6 py-4 text-left text-xs md:text-sm font-medium" style={{ color: '#9693a8' }}>User</th>
                  <th className="px-4 md:px-6 py-4 text-right text-xs md:text-sm font-medium" style={{ color: '#9693a8' }}>Volume</th>
                </tr>
              </thead>
              <tbody>
                {data.map((entry) => {
                  const stats = getStatValue(entry);
                  const isTop3 = entry.rank <= 3;
                  return (
                    <tr
                      key={entry.discord_id}
                      className="premium-table-row border-b cursor-pointer"
                      style={{ borderColor: 'rgba(160, 120, 255, 0.08)' }}
                      onClick={() => setSelectedUser(entry)}
                    >
                      <td className="px-4 md:px-6 py-4">
                        <div className={`font-bold ${isTop3 ? 'text-2xl' : 'text-lg'}`} style={{
                          color: isTop3 ? '#a883ff' : '#e8e6f0'
                        }}>
                          {getRankBadge(entry.rank)}
                        </div>
                      </td>
                      <td className="px-4 md:px-6 py-4">
                        <div className="flex items-center gap-3">
                          <Image
                            src={getAvatarUrl(entry, 48)}
                            alt={entry.username}
                            width={40}
                            height={40}
                            className="rounded-full flex-shrink-0"
                            style={{
                              border: '2px solid rgba(160, 120, 255, 0.3)'
                            }}
                          />
                          <div className="min-w-0">
                            <div className="font-semibold text-white truncate">{entry.username}</div>
                            <div className="text-xs truncate" style={{ color: '#9693a8' }}>
                              ID: {entry.discord_id.slice(0, 12)}...
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 md:px-6 py-4 text-right">
                        <div className="font-semibold" style={{ color: '#14F195' }}>
                          ${stats.volume.toLocaleString()}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </>
    );
  };

  return (
    <div className="min-h-screen relative" style={{ background: 'radial-gradient(circle at top right, #1c1528 0%, #0d0b14 70%)' }}>
      <Navbar />

      <div className="container mx-auto px-4 md:px-6 pt-24 md:pt-32 pb-12 md:pb-20">
        {/* Header */}
        <div className="mb-10 md:mb-14 text-center">
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-4 bg-gradient-to-r from-[#d7c6ff] via-[#a883ff] to-[#6d35ff] bg-clip-text text-transparent">
            Global Rankings
          </h1>
          <p className="text-base md:text-lg" style={{ color: '#b0adc0' }}>
            Top traders across the Afroo Exchange platform
          </p>
        </div>

        {/* Tabs */}
        <div className="flex flex-wrap justify-center gap-3 mb-10">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="premium-tab"
              style={{
                background: activeTab === tab.id
                  ? 'linear-gradient(135deg, rgba(168, 131, 255, 0.2), rgba(109, 53, 255, 0.2))'
                  : 'rgba(255, 255, 255, 0.03)',
                border: activeTab === tab.id
                  ? '1px solid rgba(160, 120, 255, 0.4)'
                  : '1px solid rgba(160, 120, 255, 0.15)',
                color: activeTab === tab.id ? 'white' : '#b0adc0'
              }}
            >
              <div className="text-center">
                <div className="font-semibold mb-1">{tab.name}</div>
                <div className="text-xs" style={{
                  color: activeTab === tab.id ? '#d7c6ff' : '#9693a8'
                }}>
                  {tab.description}
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Leaderboard Content */}
        <div className="animate-fadeIn">
          {getLeaderboardContent(activeTab)}
        </div>
      </div>

      {/* User Profile Modal */}
      {selectedUser && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(8px)' }}
          onClick={() => setSelectedUser(null)}
        >
          <div
            className="w-full max-w-md"
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              backdropFilter: 'blur(24px)',
              border: '1px solid rgba(160, 120, 255, 0.3)',
              borderRadius: '20px',
              padding: '32px',
              boxShadow: '0 16px 48px rgba(0, 0, 0, 0.5)'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <button
              onClick={() => setSelectedUser(null)}
              className="absolute top-4 right-4 w-10 h-10 rounded-full flex items-center justify-center transition-all"
              style={{
                background: 'rgba(255, 255, 255, 0.08)',
                border: '1px solid rgba(160, 120, 255, 0.2)',
                color: 'white'
              }}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {/* Profile Content */}
            <div className="text-center">
              <Image
                src={getAvatarUrl(selectedUser, 128)}
                alt={selectedUser.username}
                width={96}
                height={96}
                className="rounded-full mx-auto mb-4"
                style={{
                  border: '4px solid rgba(160, 120, 255, 0.4)',
                  boxShadow: '0 0 30px rgba(168, 131, 255, 0.3)'
                }}
              />

              <h2 className="text-2xl font-bold text-white mb-2">{selectedUser.username}</h2>
              {selectedUser.global_name && (
                <p className="text-sm mb-3" style={{ color: '#b0adc0' }}>{selectedUser.global_name}</p>
              )}

              <div className="inline-flex items-center px-3 py-1.5 rounded-lg mb-6 text-sm font-semibold" style={{
                background: 'rgba(168, 131, 255, 0.15)',
                color: '#a883ff',
                border: '1px solid rgba(168, 131, 255, 0.2)'
              }}>
                Rank #{selectedUser.rank}
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="p-4 rounded-xl" style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(160, 120, 255, 0.15)'
                }}>
                  <div className="text-sm mb-1" style={{ color: '#9693a8' }}>Discord ID</div>
                  <div className="text-xs font-mono text-white break-all">{selectedUser.discord_id}</div>
                </div>

                <div className="p-4 rounded-xl" style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(160, 120, 255, 0.15)'
                }}>
                  <div className="text-sm mb-1" style={{ color: '#9693a8' }}>Volume</div>
                  <div className="text-base font-bold" style={{ color: '#14F195' }}>
                    ${(selectedUser.volume_usd || 0).toLocaleString()}
                  </div>
                </div>
              </div>

              {/* Open Discord Profile Button */}
              <a
                href={`https://discord.com/users/${selectedUser.discord_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all text-white"
                style={{
                  background: 'linear-gradient(90deg, #5865F2, #7289DA)',
                  boxShadow: '0 0 20px rgba(88, 101, 242, 0.3)'
                }}
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z"/>
                </svg>
                Open Discord Profile
              </a>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .premium-tab {
          padding: 0.875rem 1.5rem;
          border-radius: 0.75rem;
          transition: all 0.3s ease;
          cursor: pointer;
          backdrop-filter: blur(20px);
          min-width: 180px;
        }

        .premium-tab:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        }

        .premium-podium-card {
          padding: 1.75rem 1.25rem;
          border-radius: 1.25rem;
          text-align: center;
          background: rgba(255, 255, 255, 0.03);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(160, 120, 255, 0.2);
          transition: all 0.3s ease;
          cursor: pointer;
        }

        .premium-podium-first {
          background: linear-gradient(135deg, rgba(168, 131, 255, 0.15), rgba(109, 53, 255, 0.15));
          border: 1px solid rgba(160, 120, 255, 0.35);
        }

        .premium-podium-card:hover {
          transform: translateY(-6px);
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }

        .premium-table-container {
          padding: 1.5rem;
          background: rgba(255, 255, 255, 0.02);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(160, 120, 255, 0.2);
          border-radius: 1.25rem;
          max-width: 6xl;
          margin: 0 auto;
        }

        .premium-table-row {
          transition: all 0.2s ease;
        }

        .premium-table-row:hover {
          background: rgba(168, 131, 255, 0.06);
        }

        .animate-fadeIn {
          animation: fadeIn 0.4s ease-out;
        }

        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @media (max-width: 768px) {
          .premium-tab {
            padding: 0.75rem 1.25rem;
            min-width: 160px;
          }

          .premium-podium-card {
            padding: 1.25rem 1rem;
          }

          .premium-table-container {
            padding: 1rem;
          }
        }
      `}</style>
    </div>
  );
}
