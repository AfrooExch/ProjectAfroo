'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import Navbar from '@/components/Navbar';
import LoginModal from '@/components/LoginModal';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/lib/api';
import { QRCodeSVG } from 'qrcode.react';
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

interface Transaction {
  id: string;
  type: 'deposit' | 'withdrawal' | 'swap';
  currency: string;
  amount: number;
  usd_value: number;
  status: string;
  timestamp: string;
  tx_hash?: string;
  from_address?: string;
  to_address?: string;
  network_fee?: string;
  server_fee?: string;
  confirmations?: number;
}

export default function WalletPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedWallet, setSelectedWallet] = useState<Wallet | null>(null);
  const [showWithdrawModal, setShowWithdrawModal] = useState(false);
  const [showReceiveModal, setShowReceiveModal] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showTxDetailsModal, setShowTxDetailsModal] = useState(false);
  const [selectedTransaction, setSelectedTransaction] = useState<Transaction | null>(null);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [generatingWallet, setGeneratingWallet] = useState(false);
  const [withdrawAddress, setWithdrawAddress] = useState('');
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [maxWithdrawFees, setMaxWithdrawFees] = useState<{network_fee: string, server_fee: string, total_deducted: string} | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'wallets' | 'transactions'>('overview');
  const [filterCurrency, setFilterCurrency] = useState<string>('all');
  const [filterType, setFilterType] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');

  const cryptoDetails: Record<string, { name: string; image: string; color: string }> = {
    'BTC': { name: 'Bitcoin', image: '/coins/BTC.png', color: '#F7931A' },
    'LTC': { name: 'Litecoin', image: '/coins/LTC.png', color: '#345D9D' },
    'ETH': { name: 'Ethereum', image: '/coins/ETH.png', color: '#627EEA' },
    'SOL': { name: 'Solana', image: '/coins/SOL.png', color: '#14F195' },
    'USDC-SOL': { name: 'USDC (Solana)', image: '/coins/USDC.png', color: '#2775CA' },
    'USDC-ETH': { name: 'USDC (Ethereum)', image: '/coins/USDC.png', color: '#2775CA' },
    'USDT-SOL': { name: 'USDT (Solana)', image: '/coins/USDT.png', color: '#26A17B' },
    'USDT-ETH': { name: 'USDT (Ethereum)', image: '/coins/USDT.png', color: '#26A17B' },
    'XRP': { name: 'Ripple', image: '/coins/XRP.png', color: '#23292F' },
    'BNB': { name: 'BNB', image: '/coins/BNB.png', color: '#F3BA2F' },
    'TRX': { name: 'Tron', image: '/coins/TRX.png', color: '#FF0013' },
    'MATIC': { name: 'Polygon', image: '/coins/MATIC.png', color: '#8247E5' },
    'DOGE': { name: 'Dogecoin', image: '/coins/DOGE.png', color: '#C2A633' },
    'AVAX': { name: 'Avalanche', image: '/coins/AVAX-BLACK.png', color: '#FFFFFF' },
  };

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      setLoading(false);
      return;
    }

    if (isAuthenticated) {
      loadWallets();
    }
  }, [isAuthenticated, isLoading]);

  useEffect(() => {
    if (wallets.length > 0) {
      loadTransactions();
    }
  }, [wallets]);

  const loadWallets = async () => {
    try {
      const data = await api.getWallets();
      const balances = (data as any).data?.balances || (data as any).balances || [];

      setWallets(balances);
    } catch (error) {
      console.error('Failed to load wallets:', error);
      toast.error('Failed to load wallets');
    } finally {
      setLoading(false);
    }
  };

  const loadTransactions = async () => {
    try {
      if (wallets.length === 0) return;

      const allTransactions: Transaction[] = [];

      for (const wallet of wallets) {
        try {
          const data = await api.get(`/api/v1/wallet/${wallet.currency}/transactions?limit=10`);
          if ((data as any).data?.transactions) {
            allTransactions.push(...(data as any).data.transactions);
          }
        } catch (error) {
        }
      }

      allTransactions.sort((a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );

      setTransactions(allTransactions.slice(0, 50));
    } catch (error) {
      console.error('Failed to load transactions:', error);
    }
  };

  const refreshWallet = async (currency?: string) => {
    setRefreshing(true);
    toast.loading('Refreshing wallet...', { id: 'refresh' });
    try {
      if (currency) {
        await api.post(`/api/v1/wallet/${currency}/sync`, {});
      } else {
        const syncPromises = wallets.map(wallet =>
          api.post(`/api/v1/wallet/${wallet.currency}/sync`, {}).catch(err => {
            console.error(`Failed to sync ${wallet.currency}:`, err);
          })
        );
        await Promise.all(syncPromises);
      }
      await loadWallets();
      await loadTransactions();
      toast.success('Wallet refreshed successfully!', { id: 'refresh' });
    } catch (error) {
      console.error('Failed to refresh wallet:', error);
      toast.error('Failed to refresh wallet', { id: 'refresh' });
    } finally {
      setRefreshing(false);
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard!`, {
      icon: '📋',
      duration: 2000,
    });
  };

  const handleMaxWithdraw = async () => {
    if (!selectedWallet) return;

    try {
      const response: any = await api.post(
        `/api/v1/wallet/${selectedWallet.currency}/withdraw/preview?amount=max`,
        { to_address: 'dummy' }
      );

      const data = response.data;
      setWithdrawAmount(data.amount);
      setMaxWithdrawFees({
        network_fee: data.network_fee,
        server_fee: data.server_fee,
        total_deducted: data.total_deducted
      });
    } catch (error: any) {
      console.error('Failed to calculate max withdrawal:', error);
      toast.error('Failed to calculate max withdrawal amount');
    }
  };

  const handleWithdraw = async () => {
    if (!selectedWallet || !withdrawAddress || !withdrawAmount) return;

    toast.loading('Processing withdrawal...', { id: 'withdraw' });
    try {
      const requestBody: any = {
        to_address: withdrawAddress,
        amount: withdrawAmount
      };

      if (maxWithdrawFees) {
        requestBody.network_fee = maxWithdrawFees.network_fee;
        requestBody.server_fee = maxWithdrawFees.server_fee;
        requestBody.total_deducted = maxWithdrawFees.total_deducted;
      }

      await api.post(`/api/v1/wallet/${selectedWallet.currency}/withdraw`, requestBody);

      toast.success('Withdrawal initiated successfully!', { id: 'withdraw' });
      setShowWithdrawModal(false);
      setWithdrawAddress('');
      setWithdrawAmount('');
      setMaxWithdrawFees(null);
      setSelectedWallet(null);

      await refreshWallet();
    } catch (error: any) {
      console.error('Withdrawal failed:', error);
      const errorMessage = error.message || error.detail || 'Withdrawal failed';
      toast.error(typeof errorMessage === 'string' ? errorMessage : 'Withdrawal failed. Please try again.', { id: 'withdraw' });
    }
  };

  const handleGenerateWallet = async (currency: string) => {
    setGeneratingWallet(true);
    toast.loading(`Generating ${currency} wallet...`, { id: 'generate' });
    try {
      const response = await api.generateWallet(currency);
      toast.success(`${currency} wallet created successfully!`, { id: 'generate' });
      setShowGenerateModal(false);
      await loadWallets();
    } catch (error: any) {
      console.error('Failed to generate wallet:', error);
      const errorMessage = error.message || error.detail || 'Failed to generate wallet';
      toast.error(typeof errorMessage === 'string' ? errorMessage : 'Failed to generate wallet. Please try again.', { id: 'generate' });
    } finally {
      setGeneratingWallet(false);
    }
  };

  const availableCurrencies = Object.keys(cryptoDetails).filter(
    currency => !wallets.find(w => w.currency === currency)
  );

  const totalBalance = wallets.reduce((sum, w) => {
    const usdValue = typeof w.usd_value === 'number' ? w.usd_value : parseFloat(w.usd_value || '0');
    return sum + usdValue;
  }, 0);

  const filteredWallets = wallets.filter(wallet => {
    const details = cryptoDetails[wallet.currency];
    const matchesSearch = searchTerm === '' ||
      wallet.currency.toLowerCase().includes(searchTerm.toLowerCase()) ||
      details?.name.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesSearch;
  });

  const filteredTransactions = transactions.filter(tx => {
    const matchesCurrency = filterCurrency === 'all' || tx.currency === filterCurrency;
    const matchesType = filterType === 'all' || tx.type === filterType;
    return matchesCurrency && matchesType;
  });

  // Get unique currencies from transactions for filter
  const uniqueCurrencies = Array.from(new Set(transactions.map(tx => tx.currency)));

  if (isLoading || loading) {
    return (
      <div className="min-h-screen" style={{ background: 'radial-gradient(circle at top right, #1c1528 0%, #0d0b14 70%)' }}>
        <Navbar />
        <div className="flex items-center justify-center min-h-[80vh]">
          <div className="relative">
            <div className="w-16 h-16 border-4 border-[#6d35ff]/20 border-t-[#a883ff] rounded-full animate-spin"></div>
            <div className="absolute inset-0 blur-xl bg-[#8f60ff] opacity-30 rounded-full animate-pulse"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen relative" style={{ background: 'radial-gradient(circle at top right, #1c1528 0%, #0d0b14 70%)' }}>
      <Toaster position="top-right" />
      <Navbar />

      {/* Login Overlay for Non-Authenticated Users */}
      {!isAuthenticated && !isLoading && (
        <div className="fixed inset-0 z-40 flex items-center justify-center p-4" style={{
          background: 'rgba(0, 0, 0, 0.7)',
          backdropFilter: 'blur(12px)'
        }}>
          <div className="premium-login-card">
            <div className="text-center">
              <div className="w-20 h-20 mx-auto mb-6 rounded-2xl flex items-center justify-center" style={{
                background: 'linear-gradient(135deg, rgba(215, 198, 255, 0.2), rgba(168, 131, 255, 0.2))',
                border: '1px solid rgba(160, 120, 255, 0.3)',
                boxShadow: '0 0 40px rgba(150, 95, 255, 0.3)'
              }}>
                <svg className="w-12 h-12 text-[#a883ff]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>

              <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">
                Wallet Access Required
              </h2>
              <p className="text-base md:text-lg mb-8" style={{ color: '#b0adc0' }}>
                Sign in with Discord to view and manage your crypto wallets
              </p>

              <button
                onClick={() => setShowLoginModal(true)}
                className="premium-btn-primary inline-flex items-center justify-center gap-3 px-8 py-4 text-lg"
              >
                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515a.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0a12.64 12.64 0 0 0-.617-1.25a.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057a19.9 19.9 0 0 0 5.993 3.03a.078.078 0 0 0 .084-.028a14.09 14.09 0 0 0 1.226-1.994a.076.076 0 0 0-.041-.106a13.107 13.107 0 0 1-1.872-.892a.077.077 0 0 1-.008-.128a10.2 10.2 0 0 0 .372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127a12.299 12.299 0 0 1-1.873.892a.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03a.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.956-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419c0-1.333.955-2.419 2.157-2.419c1.21 0 2.176 1.096 2.157 2.42c0 1.333-.946 2.418-2.157 2.418z"/>
                </svg>
                <span>Login with Discord</span>
              </button>

              <p className="text-xs mt-6" style={{ color: '#9693a8' }}>
                Secure authentication powered by Discord
              </p>
            </div>
          </div>
        </div>
      )}

      <div className={`container mx-auto px-4 md:px-6 pt-24 md:pt-32 pb-12 md:pb-20 ${!isAuthenticated && !isLoading ? 'blur-sm pointer-events-none' : ''}`}>
        {/* Header */}
        <div className="mb-8 md:mb-12 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-2 bg-gradient-to-r from-[#d7c6ff] via-[#a883ff] to-[#6d35ff] bg-clip-text text-transparent">
              My Wallet
            </h1>
            <p className="text-base md:text-lg" style={{ color: '#b0adc0' }}>
              Manage your crypto portfolio
            </p>
          </div>

          <div className="flex gap-3">
            {availableCurrencies.length > 0 && (
              <button
                onClick={() => setShowGenerateModal(true)}
                className="premium-btn-secondary flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                <span>Add Wallet</span>
              </button>
            )}
            <button
              onClick={() => refreshWallet()}
              disabled={refreshing}
              className="premium-refresh-btn"
            >
              <svg className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>{refreshing ? 'Refreshing...' : 'Refresh All'}</span>
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 md:mb-8 border-b pb-4" style={{ borderColor: 'rgba(160, 120, 255, 0.12)' }}>
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-6 py-2.5 rounded-lg font-semibold transition-all duration-300 text-sm md:text-base ${
              activeTab === 'overview'
                ? 'bg-gradient-to-r from-[#d7c6ff] via-[#a883ff] to-[#6d35ff] text-white'
                : 'text-[#b0adc0] hover:text-white'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('wallets')}
            className={`px-6 py-2.5 rounded-lg font-semibold transition-all duration-300 text-sm md:text-base ${
              activeTab === 'wallets'
                ? 'bg-gradient-to-r from-[#d7c6ff] via-[#a883ff] to-[#6d35ff] text-white'
                : 'text-[#b0adc0] hover:text-white'
            }`}
          >
            Wallets
          </button>
          <button
            onClick={() => setActiveTab('transactions')}
            className={`px-6 py-2.5 rounded-lg font-semibold transition-all duration-300 text-sm md:text-base ${
              activeTab === 'transactions'
                ? 'bg-gradient-to-r from-[#d7c6ff] via-[#a883ff] to-[#6d35ff] text-white'
                : 'text-[#b0adc0] hover:text-white'
            }`}
          >
            Transactions
          </button>
        </div>

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Total Portfolio Card */}
            <div className="premium-portfolio-card">
              <div className="absolute inset-0 rounded-2xl pointer-events-none" style={{
                background: 'radial-gradient(circle at 20% 50%, rgba(168, 131, 255, 0.15), transparent 70%)'
              }}></div>

              <div className="relative z-10">
                <div className="text-sm font-medium tracking-wide mb-2" style={{ color: '#b0adc0' }}>
                  Total Portfolio Value
                </div>
                <div className="text-4xl md:text-5xl lg:text-6xl font-bold mb-3 bg-gradient-to-r from-[#d7c6ff] via-[#a883ff] to-[#6d35ff] bg-clip-text text-transparent">
                  ${totalBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>
                <div className="text-sm" style={{ color: '#9693a8' }}>
                  Across {wallets.length} active {wallets.length === 1 ? 'wallet' : 'wallets'}
                </div>
              </div>
            </div>

            {/* Balance Per Coin */}
            <div>
              <h2 className="text-2xl font-bold text-white mb-4">Balance by Currency</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {wallets.map((wallet, index) => {
                  const details = cryptoDetails[wallet.currency] || { name: wallet.currency, image: '/coins/BTC.png', color: '#a883ff' };
                  const balance = parseFloat(wallet.total || '0');
                  const usdValue = typeof wallet.usd_value === 'number' ? wallet.usd_value : parseFloat(wallet.usd_value || '0');
                  const percentage = totalBalance > 0 ? (usdValue / totalBalance * 100) : 0;

                  return (
                    <div
                      key={wallet.currency}
                      className="premium-balance-card"
                      style={{ animationDelay: `${index * 0.05}s` }}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center space-x-2">
                          <div
                            className="w-10 h-10 rounded-lg flex items-center justify-center overflow-hidden"
                            style={{
                              background: `linear-gradient(135deg, ${details.color}40, ${details.color}20)`,
                              border: `1px solid ${details.color}60`
                            }}
                          >
                            <Image
                              src={details.image}
                              alt={details.name}
                              width={28}
                              height={28}
                              className="object-contain"
                            />
                          </div>
                          <div>
                            <div className="text-sm font-bold text-white">{wallet.currency}</div>
                            <div className="text-xs" style={{ color: '#9693a8' }}>{percentage.toFixed(1)}%</div>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-1">
                        <div className="text-lg font-bold text-white">
                          {balance.toFixed(balance < 1 ? 6 : 4)}
                        </div>
                        <div className="text-sm font-semibold" style={{ color: '#14F195' }}>
                          ${usdValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </div>
                      </div>

                      <div className="mt-3 pt-3 border-t" style={{ borderColor: 'rgba(160, 120, 255, 0.12)' }}>
                        <button
                          onClick={() => {
                            setSelectedWallet(wallet);
                            setShowReceiveModal(true);
                          }}
                          className="text-xs font-semibold transition-colors"
                          style={{ color: '#a883ff' }}
                        >
                          View Address →
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Recent Transactions Preview */}
            {transactions.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-2xl font-bold text-white">Recent Activity</h2>
                  <button
                    onClick={() => setActiveTab('transactions')}
                    className="text-sm font-semibold transition-colors"
                    style={{ color: '#a883ff' }}
                  >
                    View All →
                  </button>
                </div>
                <div className="space-y-3">
                  {transactions.slice(0, 5).map((tx, index) => (
                    <div
                      key={tx.id}
                      className="premium-transaction-item"
                      style={{ animationDelay: `${index * 0.03}s` }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <div
                            className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg font-bold ${
                              tx.type === 'deposit' ? 'bg-green-500/20 text-green-400' :
                              tx.type === 'withdrawal' ? 'bg-red-500/20 text-red-400' :
                              'bg-blue-500/20 text-blue-400'
                            }`}
                          >
                            {tx.type === 'deposit' ? '↓' : tx.type === 'withdrawal' ? '↑' : '⇄'}
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-white capitalize">{tx.type} • {tx.currency}</div>
                            <div className="text-xs" style={{ color: '#9693a8' }}>
                              {(() => {
                                const date = new Date(tx.timestamp);
                                return isNaN(date.getTime()) ? 'Pending' : date.toLocaleString();
                              })()}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-sm font-bold ${
                            tx.type === 'deposit' ? 'text-green-400' : 'text-white'
                          }`}>
                            {tx.type === 'deposit' ? '+' : '-'}{(() => {
                              const amount = typeof tx.amount === 'number' ? tx.amount : parseFloat(tx.amount || '0');
                              return amount.toFixed(6);
                            })()}
                          </div>
                          <div className="text-xs" style={{ color: '#9693a8' }}>
                            ${(() => {
                              const usdValue = typeof tx.usd_value === 'number' ? tx.usd_value : parseFloat(tx.usd_value || '0');
                              return usdValue.toFixed(2);
                            })()}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Wallets Tab */}
        {activeTab === 'wallets' && (
          <>
            {/* Search Bar */}
            <div className="mb-6">
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search currencies..."
                className="w-full md:w-96 px-4 py-3 rounded-lg text-sm"
                style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(160, 120, 255, 0.2)',
                  color: '#e8e6f0'
                }}
              />
            </div>

            {filteredWallets.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 md:gap-6">
                {filteredWallets.map((wallet, index) => {
                  const details = cryptoDetails[wallet.currency] || { name: wallet.currency, image: '/coins/BTC.png', color: '#a883ff' };
                  return (
                    <div
                      key={wallet.currency}
                      className="premium-wallet-card"
                      style={{ animationDelay: `${index * 0.05}s` }}
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center space-x-3">
                          <div
                            className="w-12 h-12 rounded-xl flex items-center justify-center overflow-hidden"
                            style={{
                              background: `linear-gradient(135deg, ${details.color}40, ${details.color}20)`,
                              border: `1px solid ${details.color}60`,
                              boxShadow: `0 0 20px ${details.color}30`
                            }}
                          >
                            <Image
                              src={details.image}
                              alt={details.name}
                              width={32}
                              height={32}
                              className="object-contain"
                            />
                          </div>
                          <div>
                            <div className="text-base md:text-lg font-bold text-white">{wallet.currency}</div>
                            <div className="text-xs" style={{ color: '#9693a8' }}>{details.name}</div>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <div>
                          <div className="text-xs font-medium mb-1" style={{ color: '#b0adc0' }}>Balance</div>
                          <div className="text-xl md:text-2xl font-bold text-white">
                            {(() => {
                              const balance = parseFloat(wallet.total || '0');
                              return balance.toFixed(balance < 1 ? 6 : 4);
                            })()}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium mb-1" style={{ color: '#b0adc0' }}>USD Value</div>
                          <div className="text-base md:text-lg font-semibold" style={{ color: '#14F195' }}>
                            ${(() => {
                              const usdValue = typeof wallet.usd_value === 'number' ? wallet.usd_value : parseFloat(wallet.usd_value || '0');
                              return usdValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                            })()}
                          </div>
                        </div>
                      </div>

                      <div className="mt-4 pt-4 border-t space-y-2" style={{ borderColor: 'rgba(160, 120, 255, 0.12)' }}>
                        <div className="flex items-center justify-between">
                          <div className="text-xs" style={{ color: '#9693a8' }}>Address</div>
                          <button
                            onClick={() => copyToClipboard(wallet.address, 'Address')}
                            className="text-xs font-semibold transition-colors hover:text-white"
                            style={{ color: '#a883ff' }}
                          >
                            Copy
                          </button>
                        </div>
                        <div className="text-xs font-mono truncate" style={{ color: '#b0adc0' }}>
                          {wallet.address}
                        </div>

                        <div className="flex gap-2 pt-2">
                          <button
                            onClick={() => {
                              setSelectedWallet(wallet);
                              setShowReceiveModal(true);
                            }}
                            className="flex-1 px-3 py-2 rounded-lg text-xs font-semibold transition-all"
                            style={{
                              background: 'rgba(20, 241, 149, 0.2)',
                              color: '#14F195',
                              border: '1px solid rgba(20, 241, 149, 0.3)'
                            }}
                          >
                            Receive
                          </button>
                          <button
                            onClick={() => {
                              setSelectedWallet(wallet);
                              setShowWithdrawModal(true);
                            }}
                            className="flex-1 px-3 py-2 rounded-lg text-xs font-semibold transition-all"
                            style={{
                              background: 'rgba(168, 131, 255, 0.2)',
                              color: '#a883ff',
                              border: '1px solid rgba(168, 131, 255, 0.3)'
                            }}
                          >
                            Send
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="premium-empty-state">
                <div className="text-6xl md:text-7xl mb-6 opacity-50">💳</div>
                <h3 className="text-2xl md:text-3xl font-bold text-white mb-4">No Wallets Found</h3>
                <p className="text-base md:text-lg mb-8" style={{ color: '#b0adc0' }}>
                  {searchTerm ? 'Try a different search term' : 'Your wallets will appear here once created'}
                </p>
              </div>
            )}
          </>
        )}

        {/* Transaction History Tab */}
        {activeTab === 'transactions' && (
          <div className="space-y-4">
            {/* Filters */}
            <div className="flex flex-col sm:flex-row gap-3">
              <select
                value={filterCurrency}
                onChange={(e) => setFilterCurrency(e.target.value)}
                className="px-4 py-2 rounded-lg text-sm"
                style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(160, 120, 255, 0.2)',
                  color: '#e8e6f0'
                }}
              >
                <option value="all">All Currencies</option>
                {uniqueCurrencies.map(currency => (
                  <option key={currency} value={currency}>{currency}</option>
                ))}
              </select>

              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="px-4 py-2 rounded-lg text-sm"
                style={{
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(160, 120, 255, 0.2)',
                  color: '#e8e6f0'
                }}
              >
                <option value="all">All Types</option>
                <option value="deposit">Deposits</option>
                <option value="withdrawal">Withdrawals</option>
                <option value="swap">Swaps</option>
              </select>
            </div>

            {/* Transactions List */}
            <div className="premium-transactions-container">
              {filteredTransactions.length > 0 ? (
                <div className="space-y-3">
                  {filteredTransactions.map((tx, index) => (
                    <div
                      key={tx.id}
                      className="premium-transaction-item cursor-pointer hover:bg-white/5 transition-colors"
                      style={{ animationDelay: `${index * 0.03}s` }}
                      onClick={() => {
                        setSelectedTransaction(tx);
                        setShowTxDetailsModal(true);
                      }}
                    >
                      <div className="flex items-center space-x-4">
                        <div
                          className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg font-bold ${
                            tx.type === 'deposit' ? 'bg-green-500/20 text-green-400' :
                            tx.type === 'withdrawal' ? 'bg-red-500/20 text-red-400' :
                            'bg-blue-500/20 text-blue-400'
                          }`}
                        >
                          {tx.type === 'deposit' ? '↓' : tx.type === 'withdrawal' ? '↑' : '⇄'}
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm md:text-base font-semibold text-white capitalize">{tx.type}</span>
                            <span className="text-xs px-2 py-0.5 rounded-full capitalize" style={{
                              background: tx.status === 'completed' ? 'rgba(20, 241, 149, 0.2)' :
                                        tx.status === 'pending' ? 'rgba(255, 193, 7, 0.2)' :
                                        tx.status === 'failed' ? 'rgba(244, 67, 54, 0.2)' : 'rgba(168, 131, 255, 0.2)',
                              color: tx.status === 'completed' ? '#14F195' :
                                   tx.status === 'pending' ? '#ffc107' :
                                   tx.status === 'failed' ? '#f44336' : '#a883ff'
                            }}>
                              {tx.status}
                            </span>
                          </div>
                          <div className="text-xs md:text-sm" style={{ color: '#9693a8' }}>
                            {(() => {
                              const date = new Date(tx.timestamp);
                              return isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleString();
                            })()}
                          </div>
                        </div>

                        <div className="text-right">
                          <div className={`text-sm md:text-base font-bold ${
                            tx.type === 'deposit' ? 'text-green-400' : 'text-white'
                          }`}>
                            {tx.type === 'deposit' ? '+' : '-'}{(() => {
                              const amount = typeof tx.amount === 'number' ? tx.amount : parseFloat(tx.amount || '0');
                              return amount.toFixed(6);
                            })()} {tx.currency}
                          </div>
                          <div className="text-xs md:text-sm" style={{ color: '#9693a8' }}>
                            ${(() => {
                              const usdValue = typeof tx.usd_value === 'number' ? tx.usd_value : parseFloat(tx.usd_value || '0');
                              return usdValue.toFixed(2);
                            })()}
                          </div>
                        </div>
                      </div>

                      {tx.tx_hash && (
                        <div className="mt-2 pt-2 border-t flex items-center justify-between" style={{ borderColor: 'rgba(160, 120, 255, 0.08)' }}>
                          <div className="text-xs font-mono truncate flex-1" style={{ color: '#9693a8' }}>
                            TX: {tx.tx_hash}
                          </div>
                          <button
                            onClick={() => copyToClipboard(tx.tx_hash!, 'Transaction hash')}
                            className="text-xs font-semibold ml-2 transition-colors hover:text-white"
                            style={{ color: '#a883ff' }}
                          >
                            Copy
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="premium-empty-state">
                  <div className="text-6xl md:text-7xl mb-6 opacity-50">📊</div>
                  <h3 className="text-2xl md:text-3xl font-bold text-white mb-4">No Transactions Found</h3>
                  <p className="text-base md:text-lg" style={{ color: '#b0adc0' }}>
                    {filterCurrency !== 'all' || filterType !== 'all'
                      ? 'Try adjusting your filters'
                      : 'Your transaction history will appear here'}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Receive Modal (QR Code) */}
        {showReceiveModal && selectedWallet && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: 'rgba(0, 0, 0, 0.85)', backdropFilter: 'blur(8px)' }}
            onClick={() => setShowReceiveModal(false)}
          >
            <div
              className="premium-modal"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl md:text-3xl font-bold text-white">
                  Receive {selectedWallet.currency}
                </h2>
                <button
                  onClick={() => setShowReceiveModal(false)}
                  className="text-gray-400 hover:text-white text-3xl transition-colors w-10 h-10 flex items-center justify-center rounded-lg hover:bg-white/5"
                >
                  ×
                </button>
              </div>

              <div className="space-y-6">
                {/* QR Code */}
                <div className="flex justify-center p-6 rounded-2xl" style={{
                  background: 'white'
                }}>
                  <QRCodeSVG
                    value={selectedWallet.address}
                    size={220}
                    level="H"
                    includeMargin={true}
                  />
                </div>

                {/* Address */}
                <div>
                  <div className="text-sm font-medium mb-2" style={{ color: '#b0adc0' }}>
                    Deposit Address
                  </div>
                  <div className="flex flex-col sm:flex-row gap-2">
                    <input
                      type="text"
                      value={selectedWallet.address}
                      readOnly
                      className="input flex-1 font-mono text-xs md:text-sm"
                      style={{
                        background: 'rgba(255, 255, 255, 0.03)',
                        border: '1px solid rgba(160, 120, 255, 0.2)',
                        color: '#e8e6f0'
                      }}
                    />
                    <button
                      onClick={() => copyToClipboard(selectedWallet.address, 'Address')}
                      className="premium-btn-primary px-6 py-3 whitespace-nowrap"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                      <span>Copy</span>
                    </button>
                  </div>
                </div>

                {/* Warning */}
                <div className="p-4 rounded-lg" style={{
                  background: 'rgba(255, 193, 7, 0.1)',
                  border: '1px solid rgba(255, 193, 7, 0.3)'
                }}>
                  <div className="flex items-start gap-3">
                    <svg className="w-5 h-5 flex-shrink-0" style={{ color: '#ffc107' }} fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    <div className="text-xs" style={{ color: '#ffc107' }}>
                      Only send {selectedWallet.currency} to this address. Sending any other currency may result in permanent loss.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Withdraw/Send Modal */}
        {showWithdrawModal && selectedWallet && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: 'rgba(0, 0, 0, 0.85)', backdropFilter: 'blur(8px)' }}
            onClick={() => setShowWithdrawModal(false)}
          >
            <div
              className="premium-modal"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl md:text-3xl font-bold text-white">
                  Send {selectedWallet.currency}
                </h2>
                <button
                  onClick={() => setShowWithdrawModal(false)}
                  className="text-gray-400 hover:text-white text-3xl transition-colors w-10 h-10 flex items-center justify-center rounded-lg hover:bg-white/5"
                >
                  ×
                </button>
              </div>

              <div className="space-y-6">
                {/* Balance Info */}
                <div className="p-4 rounded-lg" style={{
                  background: 'rgba(168, 131, 255, 0.1)',
                  border: '1px solid rgba(168, 131, 255, 0.2)'
                }}>
                  <div className="text-xs mb-1" style={{ color: '#b0adc0' }}>Available Balance</div>
                  <div className="text-2xl font-bold text-white">
                    {parseFloat(selectedWallet.total || '0').toFixed(8)} {selectedWallet.currency}
                  </div>
                  <div className="text-sm" style={{ color: '#14F195' }}>
                    ≈ ${(() => {
                      const usdValue = typeof selectedWallet.usd_value === 'number' ? selectedWallet.usd_value : parseFloat(selectedWallet.usd_value || '0');
                      return usdValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                    })()}
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium mb-2 block" style={{ color: '#b0adc0' }}>
                    Recipient Address
                  </label>
                  <input
                    type="text"
                    value={withdrawAddress}
                    onChange={(e) => setWithdrawAddress(e.target.value)}
                    placeholder="Enter recipient address"
                    className="input w-full font-mono text-sm"
                    style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(160, 120, 255, 0.2)',
                      color: '#e8e6f0'
                    }}
                  />
                </div>

                <div>
                  <label className="text-sm font-medium mb-2 block" style={{ color: '#b0adc0' }}>
                    Amount
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="number"
                      value={withdrawAmount}
                      onChange={(e) => {
                        setWithdrawAmount(e.target.value);
                        setMaxWithdrawFees(null); // Clear fees when amount is manually changed
                      }}
                      placeholder="0.00"
                      step="any"
                      className="input flex-1"
                      style={{
                        background: 'rgba(255, 255, 255, 0.03)',
                        border: '1px solid rgba(160, 120, 255, 0.2)',
                        color: '#e8e6f0'
                      }}
                    />
                    <button
                      onClick={handleMaxWithdraw}
                      className="px-4 py-2 rounded-lg font-semibold text-sm transition-all"
                      style={{
                        background: 'rgba(168, 131, 255, 0.2)',
                        color: '#a883ff',
                        border: '1px solid rgba(168, 131, 255, 0.3)'
                      }}
                    >
                      MAX
                    </button>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row gap-3 pt-4">
                  <button
                    onClick={() => setShowWithdrawModal(false)}
                    className="premium-btn-secondary flex-1"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleWithdraw}
                    disabled={!withdrawAddress || !withdrawAmount || parseFloat(withdrawAmount) <= 0}
                    className="premium-btn-primary flex-1"
                    style={{
                      opacity: (!withdrawAddress || !withdrawAmount || parseFloat(withdrawAmount) <= 0) ? 0.5 : 1
                    }}
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                    <span>Send {selectedWallet.currency}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Transaction Details Modal */}
        {showTxDetailsModal && selectedTransaction && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={() => setShowTxDetailsModal(false)}>
            <div className="premium-modal" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-white">Transaction Details</h2>
                <button
                  onClick={() => setShowTxDetailsModal(false)}
                  className="text-white/60 hover:text-white transition-colors"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-4">
                {/* Type & Status */}
                <div className="flex items-center justify-between p-4 rounded-lg" style={{ background: 'rgba(255, 255, 255, 0.03)' }}>
                  <div>
                    <div className="text-sm" style={{ color: '#9693a8' }}>Type</div>
                    <div className="text-lg font-semibold text-white capitalize flex items-center gap-2 mt-1">
                      <span className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        selectedTransaction.type === 'deposit' ? 'bg-green-500/20 text-green-400' :
                        selectedTransaction.type === 'withdrawal' ? 'bg-red-500/20 text-red-400' :
                        'bg-blue-500/20 text-blue-400'
                      }`}>
                        {selectedTransaction.type === 'deposit' ? '↓' : selectedTransaction.type === 'withdrawal' ? '↑' : '⇄'}
                      </span>
                      {selectedTransaction.type}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm" style={{ color: '#9693a8' }}>Status</div>
                    <span className="inline-block text-sm px-3 py-1 rounded-full capitalize mt-1 font-semibold" style={{
                      background: selectedTransaction.status === 'completed' ? 'rgba(20, 241, 149, 0.2)' :
                                selectedTransaction.status === 'pending' ? 'rgba(255, 193, 7, 0.2)' :
                                selectedTransaction.status === 'failed' ? 'rgba(244, 67, 54, 0.2)' : 'rgba(168, 131, 255, 0.2)',
                      color: selectedTransaction.status === 'completed' ? '#14F195' :
                           selectedTransaction.status === 'pending' ? '#ffc107' :
                           selectedTransaction.status === 'failed' ? '#f44336' : '#a883ff'
                    }}>
                      {selectedTransaction.status}
                    </span>
                  </div>
                </div>

                {/* Amount */}
                <div className="p-4 rounded-lg" style={{ background: 'rgba(255, 255, 255, 0.03)' }}>
                  <div className="text-sm mb-2" style={{ color: '#9693a8' }}>Amount</div>
                  <div className={`text-2xl font-bold ${selectedTransaction.type === 'deposit' ? 'text-green-400' : 'text-white'}`}>
                    {selectedTransaction.type === 'deposit' ? '+' : '-'}{(() => {
                      const amount = typeof selectedTransaction.amount === 'number' ? selectedTransaction.amount : parseFloat(selectedTransaction.amount || '0');
                      return amount.toFixed(6);
                    })()} {selectedTransaction.currency}
                  </div>
                  <div className="text-sm mt-1" style={{ color: '#9693a8' }}>
                    ≈ ${(() => {
                      const usdValue = typeof selectedTransaction.usd_value === 'number' ? selectedTransaction.usd_value : parseFloat(selectedTransaction.usd_value || '0');
                      return usdValue.toFixed(2);
                    })()} USD
                  </div>
                </div>

                {/* Timestamp */}
                <div className="p-4 rounded-lg" style={{ background: 'rgba(255, 255, 255, 0.03)' }}>
                  <div className="text-sm mb-2" style={{ color: '#9693a8' }}>Date & Time</div>
                  <div className="text-base font-medium text-white">
                    {(() => {
                      const date = new Date(selectedTransaction.timestamp);
                      return isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleString();
                    })()}
                  </div>
                </div>

                {/* Transaction Hash */}
                {selectedTransaction.tx_hash && (
                  <div className="p-4 rounded-lg" style={{ background: 'rgba(255, 255, 255, 0.03)' }}>
                    <div className="text-sm mb-2" style={{ color: '#9693a8' }}>Transaction Hash</div>
                    <div className="flex items-center gap-2">
                      <div className="text-sm font-mono break-all flex-1 text-white">
                        {selectedTransaction.tx_hash}
                      </div>
                      <button
                        onClick={() => copyToClipboard(selectedTransaction.tx_hash!, 'Transaction hash')}
                        className="px-3 py-1.5 rounded-lg text-sm font-semibold transition-all hover:scale-105"
                        style={{ background: 'rgba(168, 131, 255, 0.2)', color: '#a883ff' }}
                      >
                        Copy
                      </button>
                    </div>
                  </div>
                )}

                {/* From Address */}
                {selectedTransaction.from_address && (
                  <div className="p-4 rounded-lg" style={{ background: 'rgba(255, 255, 255, 0.03)' }}>
                    <div className="text-sm mb-2" style={{ color: '#9693a8' }}>From Address</div>
                    <div className="flex items-center gap-2">
                      <div className="text-sm font-mono break-all flex-1 text-white">
                        {selectedTransaction.from_address}
                      </div>
                      <button
                        onClick={() => copyToClipboard(selectedTransaction.from_address!, 'From address')}
                        className="px-3 py-1.5 rounded-lg text-sm font-semibold transition-all hover:scale-105"
                        style={{ background: 'rgba(168, 131, 255, 0.2)', color: '#a883ff' }}
                      >
                        Copy
                      </button>
                    </div>
                  </div>
                )}

                {/* To Address */}
                {selectedTransaction.to_address && (
                  <div className="p-4 rounded-lg" style={{ background: 'rgba(255, 255, 255, 0.03)' }}>
                    <div className="text-sm mb-2" style={{ color: '#9693a8' }}>To Address</div>
                    <div className="flex items-center gap-2">
                      <div className="text-sm font-mono break-all flex-1 text-white">
                        {selectedTransaction.to_address}
                      </div>
                      <button
                        onClick={() => copyToClipboard(selectedTransaction.to_address!, 'To address')}
                        className="px-3 py-1.5 rounded-lg text-sm font-semibold transition-all hover:scale-105"
                        style={{ background: 'rgba(168, 131, 255, 0.2)', color: '#a883ff' }}
                      >
                        Copy
                      </button>
                    </div>
                  </div>
                )}

                {/* Fees */}
                {(selectedTransaction.network_fee || selectedTransaction.server_fee) && (
                  <div className="p-4 rounded-lg space-y-2" style={{ background: 'rgba(255, 255, 255, 0.03)' }}>
                    <div className="text-sm mb-3" style={{ color: '#9693a8' }}>Fees</div>
                    {selectedTransaction.network_fee && (
                      <div className="flex justify-between">
                        <span className="text-sm text-white/80">Network Fee:</span>
                        <span className="text-sm font-semibold text-white">{selectedTransaction.network_fee} {selectedTransaction.currency}</span>
                      </div>
                    )}
                    {selectedTransaction.server_fee && (
                      <div className="flex justify-between">
                        <span className="text-sm text-white/80">Server Fee:</span>
                        <span className="text-sm font-semibold text-white">{selectedTransaction.server_fee} {selectedTransaction.currency}</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Confirmations */}
                {selectedTransaction.confirmations !== undefined && (
                  <div className="p-4 rounded-lg" style={{ background: 'rgba(255, 255, 255, 0.03)' }}>
                    <div className="text-sm mb-2" style={{ color: '#9693a8' }}>Confirmations</div>
                    <div className="text-base font-semibold text-white">
                      {selectedTransaction.confirmations}
                    </div>
                  </div>
                )}
              </div>

              <button
                onClick={() => setShowTxDetailsModal(false)}
                className="premium-btn-secondary w-full mt-6"
              >
                Close
              </button>
            </div>
          </div>
        )}

        {/* Generate Wallet Modal */}
        {showGenerateModal && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={() => setShowGenerateModal(false)}>
            <div className="premium-modal max-w-2xl" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-white">Add New Wallet</h2>
                <button
                  onClick={() => setShowGenerateModal(false)}
                  className="text-white/60 hover:text-white transition-colors"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <p className="text-sm mb-6" style={{ color: '#9693a8' }}>
                Select a currency to create a new wallet. Your wallet will be generated instantly and ready to receive funds.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-96 overflow-y-auto">
                {availableCurrencies.map((currency) => {
                  const details = cryptoDetails[currency];
                  return (
                    <button
                      key={currency}
                      onClick={() => handleGenerateWallet(currency)}
                      disabled={generatingWallet}
                      className="p-4 rounded-xl border transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
                      style={{
                        background: 'rgba(255, 255, 255, 0.03)',
                        borderColor: 'rgba(160, 120, 255, 0.2)',
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className="w-12 h-12 rounded-lg flex items-center justify-center overflow-hidden"
                          style={{
                            background: `linear-gradient(135deg, ${details.color}40, ${details.color}20)`,
                            border: `1px solid ${details.color}60`
                          }}
                        >
                          <Image
                            src={details.image}
                            alt={details.name}
                            width={32}
                            height={32}
                            className="object-contain"
                          />
                        </div>
                        <div className="text-left flex-1">
                          <div className="text-sm font-bold text-white">{currency}</div>
                          <div className="text-xs" style={{ color: '#9693a8' }}>{details.name}</div>
                        </div>
                        <svg className="w-5 h-5 text-white/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </div>
                    </button>
                  );
                })}
              </div>

              {availableCurrencies.length === 0 && (
                <div className="text-center py-8">
                  <div className="text-4xl mb-3">🎉</div>
                  <p className="text-white font-semibold mb-1">All wallets created!</p>
                  <p className="text-sm" style={{ color: '#9693a8' }}>You have wallets for all supported currencies.</p>
                </div>
              )}

              <button
                onClick={() => setShowGenerateModal(false)}
                className="premium-btn-secondary w-full mt-6"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .premium-refresh-btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 0.5rem;
          padding: 0.75rem 1.5rem;
          font-size: 0.875rem;
          font-weight: 600;
          color: #e8e6f0;
          background: rgba(255, 255, 255, 0.03);
          backdrop-filter: blur(16px);
          border: 1.5px solid rgba(160, 120, 255, 0.25);
          border-radius: 0.75rem;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .premium-refresh-btn:hover:not(:disabled) {
          background: rgba(255, 255, 255, 0.06);
          border-color: rgba(160, 120, 255, 0.45);
          transform: translateY(-2px);
          box-shadow: 0 0 20px rgba(150, 95, 255, 0.25);
        }

        .premium-refresh-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .premium-portfolio-card {
          position: relative;
          padding: 2rem;
          background: rgba(255, 255, 255, 0.02);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(160, 120, 255, 0.15);
          border-radius: 1.5rem;
          overflow: hidden;
        }

        .premium-balance-card {
          position: relative;
          padding: 1.25rem;
          background: rgba(255, 255, 255, 0.02);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(160, 120, 255, 0.12);
          border-radius: 1rem;
          transition: all 0.3s ease;
          animation: fadeInScale 0.4s ease-out forwards;
          opacity: 0;
        }

        .premium-balance-card:hover {
          transform: translateY(-4px);
          border-color: rgba(160, 120, 255, 0.25);
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2), 0 0 20px rgba(150, 95, 255, 0.15);
        }

        .premium-wallet-card {
          position: relative;
          padding: 1.5rem;
          background: rgba(255, 255, 255, 0.02);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(160, 120, 255, 0.12);
          border-radius: 1.25rem;
          transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          animation: fadeInScale 0.5s ease-out forwards;
          opacity: 0;
        }

        .premium-wallet-card:hover {
          transform: translateY(-6px);
          border-color: rgba(160, 120, 255, 0.3);
          box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3), 0 0 30px rgba(150, 95, 255, 0.2);
        }

        .premium-transactions-container {
          background: rgba(255, 255, 255, 0.02);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(160, 120, 255, 0.12);
          border-radius: 1.25rem;
          padding: 1.5rem;
        }

        .premium-transaction-item {
          padding: 1rem;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(160, 120, 255, 0.1);
          border-radius: 0.75rem;
          transition: all 0.3s ease;
          animation: fadeInScale 0.4s ease-out forwards;
          opacity: 0;
        }

        .premium-transaction-item:hover {
          background: rgba(255, 255, 255, 0.05);
          border-color: rgba(160, 120, 255, 0.2);
        }

        .premium-empty-state {
          text-align: center;
          padding: 4rem 2rem;
          background: rgba(255, 255, 255, 0.02);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(160, 120, 255, 0.12);
          border-radius: 1.5rem;
        }

        .premium-modal {
          position: relative;
          background: rgba(13, 11, 20, 0.95);
          backdrop-filter: blur(24px);
          border: 1px solid rgba(160, 120, 255, 0.25);
          border-radius: 1.5rem;
          padding: 2rem;
          max-width: 600px;
          width: 100%;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 40px rgba(150, 95, 255, 0.2);
          max-height: 90vh;
          overflow-y: auto;
        }

        .premium-btn-primary {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 0.5rem;
          padding: 1rem 2rem;
          font-size: 1rem;
          font-weight: 600;
          color: white;
          background: linear-gradient(135deg, #d7c6ff, #a883ff, #6d35ff);
          border-radius: 0.875rem;
          transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          box-shadow: 0 0 20px rgba(150, 95, 255, 0.3), 0 8px 24px rgba(0, 0, 0, 0.15);
          border: none;
          cursor: pointer;
        }

        .premium-btn-primary:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 0 32px rgba(150, 95, 255, 0.5), 0 12px 32px rgba(0, 0, 0, 0.2);
        }

        .premium-btn-primary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .premium-btn-secondary {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 0.5rem;
          padding: 1rem 2rem;
          font-size: 1rem;
          font-weight: 600;
          color: #e8e6f0;
          background: rgba(255, 255, 255, 0.03);
          backdrop-filter: blur(16px);
          border: 1.5px solid rgba(160, 120, 255, 0.25);
          border-radius: 0.875rem;
          transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
          cursor: pointer;
        }

        .premium-btn-secondary:hover {
          background: rgba(255, 255, 255, 0.06);
          border-color: rgba(160, 120, 255, 0.45);
          transform: translateY(-2px);
          box-shadow: 0 0 20px rgba(150, 95, 255, 0.25);
        }

        @keyframes fadeInScale {
          from {
            opacity: 0;
            transform: scale(0.95) translateY(10px);
          }
          to {
            opacity: 1;
            transform: scale(1) translateY(0);
          }
        }

        .premium-login-card {
          position: relative;
          background: rgba(13, 11, 20, 0.95);
          backdrop-filter: blur(24px);
          border: 1px solid rgba(160, 120, 255, 0.25);
          border-radius: 1.5rem;
          padding: 3rem 2rem;
          max-width: 500px;
          width: 100%;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 40px rgba(150, 95, 255, 0.2);
          animation: fadeInScale 0.5s ease-out forwards;
        }

        @media (max-width: 768px) {
          .premium-portfolio-card {
            padding: 1.5rem;
          }

          .premium-modal {
            padding: 1.5rem;
          }

          .premium-login-card {
            padding: 2rem 1.5rem;
          }
        }
      `}</style>

      {/* Login Modal */}
      <LoginModal isOpen={showLoginModal} onClose={() => setShowLoginModal(false)} />
    </div>
  );
}
 
