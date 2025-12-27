'use client';

import { useEffect, useState } from 'react';
import Navbar from '@/components/Navbar';
import CryptoIcon from '@/components/CryptoIcon';
import { useAuth } from '@/contexts/AuthContext';
import LoginModal from '@/components/LoginModal';
import api from '@/lib/api';
import toast, { Toaster } from 'react-hot-toast';
import { QRCodeSVG } from 'qrcode.react';

interface SupportedAsset {
  code: string;
  name: string;
  network?: string;
  hasExternalId?: boolean;
  isFiat?: boolean;
  featured?: boolean;
  isStable?: boolean;
}

interface SwapHistory {
  id: string;
  from_asset: string;
  to_asset: string;
  amount: number;
  estimated_output: number;
  status: string;
  created_at: string;
  destination_address: string;
}

interface SwapQuote {
  from_asset: string;
  to_asset: string;
  input_amount: number;
  estimated_output: number;
  exchange_rate: number;
  platform_fee_percent: number;
  platform_fee_units: number;
  changenow_network_fee: number;
  changenow_service_fee: number;
  valid_until: string;
}

export default function SwapPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [fromCurrency, setFromCurrency] = useState('BTC');
  const [toCurrency, setToCurrency] = useState('ETH');
  const [amount, setAmount] = useState('');
  const [toAddress, setToAddress] = useState('');
  const [refundAddress, setRefundAddress] = useState('');
  const [slippageTolerance, setSlippageTolerance] = useState('1');

  const [supportedAssets, setSupportedAssets] = useState<SupportedAsset[]>([]);
  const [loadingAssets, setLoadingAssets] = useState(true);
  const [quote, setQuote] = useState<SwapQuote | null>(null);
  const [quoting, setQuoting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeSwap, setActiveSwap] = useState<any>(null);
  const [swapHistory, setSwapHistory] = useState<SwapHistory[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showFromDropdown, setShowFromDropdown] = useState(false);
  const [showToDropdown, setShowToDropdown] = useState(false);
  const [searchFrom, setSearchFrom] = useState('');
  const [searchTo, setSearchTo] = useState('');
  const [showLoginModal, setShowLoginModal] = useState(false);

  // Status polling
  const [swapStatus, setSwapStatus] = useState<string>('pending');
  const [statusPolling, setStatusPolling] = useState<NodeJS.Timeout | null>(null);
  const [txHash, setTxHash] = useState<string>('');
  const [notificationPermission, setNotificationPermission] = useState<NotificationPermission>('default');
  const [quoteValidUntil, setQuoteValidUntil] = useState<Date | null>(null);
  const [timeRemaining, setTimeRemaining] = useState<number>(0);

  // USD price converter
  const [usdPrices, setUsdPrices] = useState<Record<string, number>>({});
  const [loadingPrices, setLoadingPrices] = useState(false);

  useEffect(() => {
    loadSupportedAssets();

    // Restore active swap from localStorage
    if (typeof window !== 'undefined') {
      const savedSwap = localStorage.getItem('activeSwap');
      if (savedSwap) {
        try {
          const swap = JSON.parse(savedSwap);
          setActiveSwap(swap);
          setSwapStatus(swap.changenow_status || swap.status || 'pending');
          setFromCurrency(swap.from_asset || 'BTC');
          setToCurrency(swap.to_asset || 'ETH');
          setAmount(swap.amount?.toString() || '');
          setToAddress(swap.destination_address || '');
          toast.success('Restored active swap!');
        } catch (error) {
          console.error('Failed to restore swap from localStorage:', error);
          localStorage.removeItem('activeSwap');
        }
      }
    }

    if (typeof window !== 'undefined' && 'Notification' in window) {
      setNotificationPermission(Notification.permission);
      if (Notification.permission === 'default') {
        Notification.requestPermission().then(permission => {
          setNotificationPermission(permission);
        });
      }
    }
  }, []);

  useEffect(() => {
    if (quoteValidUntil) {
      const interval = setInterval(() => {
        const now = new Date().getTime();
        const expiry = quoteValidUntil.getTime();
        const remaining = Math.max(0, Math.floor((expiry - now) / 1000));
        setTimeRemaining(remaining);

        if (remaining === 0) {
          clearInterval(interval);
          toast.error('Quote expired. Please get a new quote.');
          setQuote(null);
        }
      }, 1000);

      return () => clearInterval(interval);
    }
  }, [quoteValidUntil]);

  useEffect(() => {
    if (activeSwap && activeSwap._id) {
      const interval = setInterval(() => {
        pollStatus();
      }, 10000);

      setStatusPolling(interval);

      return () => {
        if (interval) clearInterval(interval);
      };
    } else {
      if (statusPolling) {
        clearInterval(statusPolling);
        setStatusPolling(null);
      }
    }
  }, [activeSwap]);

  const pollStatus = async () => {
    if (!activeSwap || !activeSwap._id) return;

    try {
      const data = await api.get(`/api/v1/afroo-swaps/${activeSwap._id}?refresh=true`);
      const newStatus = (data as any).changenow_status || (data as any).status || 'pending';
      const hash = (data as any).changenow_payout_hash || (data as any).payout_hash || (data as any).payoutHash || '';

      if (hash && hash !== txHash) {
        setTxHash(hash);
      }

      const previousStatus = swapStatus;
      if (newStatus !== previousStatus && notificationPermission === 'granted') {
        const statusMessages: Record<string, string> = {
          'waiting': '✅ Deposit received! Processing your swap...',
          'confirming': '🔄 Confirming your transaction...',
          'exchanging': '💱 Exchanging your crypto...',
          'sending': '📤 Sending to your wallet...',
          'finished': '🎉 Swap completed successfully!',
          'completed': '🎉 Swap completed successfully!',
          'failed': '❌ Swap failed. Check for refund.',
          'expired': '⏰ Swap expired. No funds received.'
        };

        if (statusMessages[newStatus]) {
          new Notification('Afroo Swap Update', {
            body: statusMessages[newStatus],
            icon: '/favicon.ico',
            badge: '/favicon.ico'
          });
        }
      }

      setSwapStatus(newStatus);

      // Update activeSwap with latest data
      setActiveSwap((data as any));

      // Save to localStorage
      if (typeof window !== 'undefined') {
        localStorage.setItem('activeSwap', JSON.stringify(data));
      }

      if (['finished', 'completed', 'failed', 'expired'].includes(newStatus)) {
        if (statusPolling) {
          clearInterval(statusPolling);
          setStatusPolling(null);
        }
        // Clear localStorage after completion
        if (typeof window !== 'undefined') {
          localStorage.removeItem('activeSwap');
        }
      }
    } catch (error) {
      console.error('Failed to poll swap status:', error);
    }
  };

  const loadSupportedAssets = async () => {
    try {
      const data = await api.get('/api/v1/afroo-swaps/supported-assets');
      setSupportedAssets((data as any).assets || []);
    } catch (error) {
      toast.error('Failed to load supported assets');
    } finally {
      setLoadingAssets(false);
    }
  };

  // Fetch USD prices from CoinGecko
  const fetchUsdPrices = async (symbols: string[]) => {
    if (symbols.length === 0) return;

    setLoadingPrices(true);
    try {
      // Map crypto symbols to CoinGecko IDs
      const symbolToGeckoId: Record<string, string> = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'SOL': 'solana',
        'LTC': 'litecoin',
        'USDT': 'tether',
        'USDC': 'usd-coin',
        'BNB': 'binancecoin',
        'XRP': 'ripple',
        'ADA': 'cardano',
        'DOGE': 'dogecoin',
        'TRX': 'tron',
        'MATIC': 'matic-network',
        'DOT': 'polkadot',
        'DAI': 'dai',
        'AVAX': 'avalanche-2',
        'SHIB': 'shiba-inu',
        'ATOM': 'cosmos',
        'UNI': 'uniswap'
      };

      const geckoIds = symbols
        .map(s => s.split('-')[0]) // Remove network suffix
        .map(s => symbolToGeckoId[s])
        .filter(Boolean);

      if (geckoIds.length === 0) return;

      const response = await fetch(
        `https://api.coingecko.com/api/v3/simple/price?ids=${geckoIds.join(',')}&vs_currencies=usd`
      );

      if (!response.ok) {
        console.error('Failed to fetch USD prices');
        return;
      }

      const data = await response.json();

      // Map back to symbols
      const prices: Record<string, number> = {};
      symbols.forEach(symbol => {
        const baseSymbol = symbol.split('-')[0];
        const geckoId = symbolToGeckoId[baseSymbol];
        if (geckoId && data[geckoId]?.usd) {
          prices[symbol] = data[geckoId].usd;
        }
      });

      setUsdPrices(prices);
    } catch (error) {
      console.error('Error fetching USD prices:', error);
    } finally {
      setLoadingPrices(false);
    }
  };

  // Fetch prices when currencies change
  useEffect(() => {
    if (fromCurrency && toCurrency) {
      fetchUsdPrices([fromCurrency, toCurrency]);
    }
  }, [fromCurrency, toCurrency]);

  // Helper function to format USD value
  const formatUSD = (cryptoAmount: number, symbol: string): string => {
    const price = usdPrices[symbol];
    if (!price) return '';
    const usdValue = cryptoAmount * price;
    return usdValue.toLocaleString('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  };

  const filteredFromCryptos = supportedAssets.filter((c) =>
    c.code.toLowerCase().includes(searchFrom.toLowerCase()) ||
    c.name.toLowerCase().includes(searchFrom.toLowerCase())
  );

  const filteredToCryptos = supportedAssets.filter((c) =>
    c.code.toLowerCase().includes(searchTo.toLowerCase()) ||
    c.name.toLowerCase().includes(searchTo.toLowerCase())
  );

  const swapCurrencies = () => {
    const temp = fromCurrency;
    setFromCurrency(toCurrency);
    setToCurrency(temp);
    setQuote(null);
  };

  useEffect(() => {
    if (amount && parseFloat(amount) > 0 && fromCurrency && toCurrency) {
      const delayDebounce = setTimeout(() => {
        getQuote();
      }, 500);
      return () => clearTimeout(delayDebounce);
    } else {
      setQuote(null);
    }
  }, [amount, fromCurrency, toCurrency]);

  const getQuote = async () => {
    if (!amount || parseFloat(amount) <= 0) return;

    setQuoting(true);
    try {
      const response = await api.post('/api/v1/afroo-swaps/quote', {
        from_asset: fromCurrency,
        to_asset: toCurrency,
        amount: parseFloat(amount)
      });
      setQuote((response as any).quote);

      const validUntil = new Date();
      validUntil.setMinutes(validUntil.getMinutes() + 2);
      setQuoteValidUntil(validUntil);
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to get quote');
      setQuote(null);
    } finally {
      setQuoting(false);
    }
  };

  const handleSwap = async () => {
    if (!amount || !toAddress) {
      toast.error('Please fill in all required fields');
      return;
    }

    if (!quote) {
      toast.error('Please wait for quote to load');
      return;
    }

    setLoading(true);
    toast.loading('Creating swap...', { id: 'swap' });

    try {
      const response = await api.post('/api/v1/afroo-swaps/execute', {
        from_asset: fromCurrency,
        to_asset: toCurrency,
        amount: parseFloat(amount),
        destination_address: toAddress,
        refund_address: refundAddress || undefined,
        slippage_tolerance: parseFloat(slippageTolerance) / 100
      });
      toast.success('Swap created! Please send your payment.', { id: 'swap' });
      const swapData = (response as any).swap;
      setActiveSwap(swapData);
      setSwapStatus(swapData.changenow_status || 'pending');
      setTxHash('');

      // Save to localStorage
      if (typeof window !== 'undefined') {
        localStorage.setItem('activeSwap', JSON.stringify(swapData));
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to create swap', { id: 'swap' });
    } finally {
      setLoading(false);
    }
  };

  const renderLoadingSpinner = () => (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full"></div>
    </div>
  );

  const renderPaymentScreen = () => (
    <div className="w-full max-w-2xl mx-auto" style={{
      background: 'rgba(255, 255, 255, 0.04)',
      backdropFilter: 'blur(16px)',
      border: '1px solid rgba(255, 255, 255, 0.07)',
      borderRadius: '24px',
      padding: '32px',
      boxShadow: '0 8px 32px rgba(168, 131, 255, 0.15)'
    }}>
      {/* Status Progress Bar */}
      <div className="mb-8">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          {['pending', 'waiting', 'confirming', 'exchanging', 'sending', 'completed'].map((step, index) => {
            const statusLabels: Record<string, string> = {
              'pending': 'Awaiting',
              'waiting': 'Received',
              'confirming': 'Confirming',
              'exchanging': 'Exchanging',
              'sending': 'Sending',
              'completed': 'Complete',
              'finished': 'Complete'
            };
            // Normalize status ('finished' -> 'completed' for display)
            const normalizedStatus = swapStatus === 'finished' ? 'completed' : swapStatus;
            const currentIndex = ['pending', 'waiting', 'confirming', 'exchanging', 'sending', 'completed'].indexOf(normalizedStatus);
            const isActive = index <= currentIndex;
            const isCurrent = step === normalizedStatus;

            return (
              <div key={step} className="flex-1 flex flex-col items-center min-w-[60px]">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-2 transition-all font-semibold ${
                  isActive ? 'bg-gradient-to-r from-[#d7c6ff] via-[#a883ff] to-[#6d35ff] text-white' : 'bg-white/10 text-white/30'
                } ${isCurrent ? 'ring-4 ring-purple-400/30 animate-pulse' : ''}`}>
                  {isActive && step === 'completed' ? '✓' : index + 1}
                </div>
                <span className={`text-xs text-center font-medium ${isActive ? 'text-purple-300' : 'text-white/30'}`}>
                  {statusLabels[step]}
                </span>
              </div>
            );
          })}
        </div>
        <div style={{
          height: '6px',
          background: 'rgba(255, 255, 255, 0.1)',
          borderRadius: '999px',
          overflow: 'hidden'
        }}>
          <div
            style={{
              height: '100%',
              background: 'linear-gradient(90deg, #d7c6ff, #a883ff, #6d35ff)',
              width: `${((['pending', 'waiting', 'confirming', 'exchanging', 'sending', 'completed'].indexOf(swapStatus === 'finished' ? 'completed' : swapStatus) + 1) / 6) * 100}%`,
              transition: 'width 0.5s ease'
            }}
          />
        </div>
      </div>

      {/* Deposit Address */}
      <div className="mb-6" style={{
        padding: '16px',
        background: 'rgba(255, 255, 255, 0.05)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '12px'
      }}>
        <p className="text-xs font-semibold mb-3" style={{ color: '#a883ff' }}>DEPOSIT ADDRESS</p>
        <div className="flex items-center gap-3">
          <code className="flex-1 text-sm font-mono break-all" style={{
            background: 'rgba(0, 0, 0, 0.3)',
            padding: '10px',
            borderRadius: '8px',
            color: '#e8dbff'
          }}>
            {activeSwap.changenow_deposit_address}
          </code>
          <button
            onClick={() => {
              navigator.clipboard.writeText(activeSwap.changenow_deposit_address);
              toast.success('Address copied!');
            }}
            style={{
              padding: '10px',
              background: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: '8px',
              color: 'white',
              cursor: 'pointer',
              transition: 'all 0.3s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'rgba(168, 131, 255, 0.2)';
              e.currentTarget.style.borderColor = 'rgba(168, 131, 255, 0.5)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
              e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.15)';
            }}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </button>
        </div>
      </div>

      {/* YOU SEND / YOU RECEIVE */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <div style={{
          padding: '16px',
          background: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '12px'
        }}>
          <p className="text-xs font-semibold mb-2" style={{ color: '#a883ff' }}>YOU SEND</p>
          <p className="text-xl font-bold" style={{ color: '#e8dbff' }}>{activeSwap.input_amount} {activeSwap.from_asset}</p>
        </div>
        <div style={{
          padding: '16px',
          background: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '12px'
        }}>
          <p className="text-xs font-semibold mb-2" style={{ color: '#a883ff' }}>YOU RECEIVE</p>
          <p className="text-xl font-bold" style={{ color: '#14F195' }}>~{activeSwap.estimated_output} {activeSwap.to_asset}</p>
        </div>
      </div>

      {/* Transaction Hash */}
      {txHash && (
        <div className="mb-6" style={{
          padding: '16px',
          background: 'rgba(20, 241, 149, 0.08)',
          border: '1px solid rgba(20, 241, 149, 0.2)',
          borderRadius: '12px'
        }}>
          <p className="text-xs font-semibold mb-2" style={{ color: '#14F195' }}>TRANSACTION HASH</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-sm font-mono break-all" style={{ color: '#e8dbff' }}>{txHash}</code>
            <button
              onClick={() => {
                const explorers: Record<string, string> = {
                  'BTC': `https://blockchair.com/bitcoin/transaction/${txHash}`,
                  'ETH': `https://etherscan.io/tx/${txHash}`,
                  'SOL': `https://solscan.io/tx/${txHash}`,
                  'TRX': `https://tronscan.org/#/transaction/${txHash}`,
                  'LTC': `https://blockchair.com/litecoin/transaction/${txHash}`,
                  'XRP': `https://xrpscan.com/tx/${txHash}`
                };
                const explorerUrl = explorers[activeSwap.to_asset] || `https://blockchair.com/search?q=${txHash}`;
                window.open(explorerUrl, '_blank');
              }}
              style={{
                padding: '8px',
                background: 'rgba(255, 255, 255, 0.08)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '8px',
                color: 'white',
                cursor: 'pointer'
              }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* QR Code */}
      <div className="flex justify-center mb-6" style={{
        padding: '24px',
        background: 'rgba(255, 255, 255, 0.95)',
        borderRadius: '16px'
      }}>
        <QRCodeSVG
          value={activeSwap.changenow_deposit_address}
          size={220}
          level="H"
          includeMargin={true}
        />
      </div>

      {/* Important Notice */}
      <div className="mb-6" style={{
        padding: '16px',
        background: 'rgba(255, 193, 7, 0.08)',
        border: '1px solid rgba(255, 193, 7, 0.2)',
        borderRadius: '12px'
      }}>
        <div className="flex items-start gap-3">
          <svg className="w-5 h-5 flex-shrink-0 mt-1" style={{ color: '#ffc107' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <p className="font-semibold text-sm mb-1" style={{ color: '#ffc107' }}>Important</p>
            <p className="text-xs" style={{ color: 'rgba(255, 193, 7, 0.8)' }}>
              • Send ONLY {activeSwap.from_asset} to this address<br />
              • Sending other assets will result in permanent loss<br />
              • This swap will be tracked automatically
            </p>
          </div>
        </div>
      </div>

      <button
        onClick={() => setActiveSwap(null)}
        style={{
          width: '100%',
          padding: '14px',
          background: 'rgba(255, 255, 255, 0.08)',
          border: '1px solid rgba(168, 131, 255, 0.3)',
          borderRadius: '12px',
          color: '#e8dbff',
          fontWeight: '600',
          cursor: 'pointer',
          transition: 'all 0.3s'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'rgba(168, 131, 255, 0.15)';
          e.currentTarget.style.borderColor = 'rgba(168, 131, 255, 0.5)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
          e.currentTarget.style.borderColor = 'rgba(168, 131, 255, 0.3)';
        }}
      >
        Create Another Swap
      </button>
    </div>
  );

  const renderSwapForm = () => (
    <div className="w-full max-w-[600px] mx-auto" style={{
      background: 'rgba(255, 255, 255, 0.04)',
      backdropFilter: 'blur(16px)',
      border: '1px solid rgba(255, 255, 255, 0.07)',
      borderRadius: '24px',
      padding: '32px',
      boxShadow: '0 8px 32px rgba(168, 131, 255, 0.15)'
    }}>
      {/* FROM Section */}
      <div className="mb-6">
        <label className="block text-sm font-semibold mb-3" style={{ color: '#b8a6ff' }}>You Send</label>
        <div className="flex items-center gap-3">
          {/* Token Icon & Selector */}
          <div className="relative" style={{ width: '200px' }}>
            <button
              type="button"
              onClick={() => setShowFromDropdown(!showFromDropdown)}
              disabled={loadingAssets}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 16px',
                background: 'rgba(255, 255, 255, 0.08)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '12px',
                color: 'white',
                fontWeight: '600',
                cursor: loadingAssets ? 'not-allowed' : 'pointer',
                transition: 'all 0.3s',
                opacity: loadingAssets ? 0.5 : 1
              }}
              onMouseEnter={(e) => {
                if (!loadingAssets) {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.12)';
                  e.currentTarget.style.borderColor = 'rgba(168, 131, 255, 0.5)';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
                e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.15)';
              }}
            >
              <CryptoIcon symbol={fromCurrency} size={28} />
              <span className="flex-1 text-left">{fromCurrency}</span>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {showFromDropdown && (
              <div style={{
                position: 'absolute',
                top: 'calc(100% + 8px)',
                left: 0,
                right: 0,
                padding: '12px',
                background: 'rgba(13, 11, 20, 0.98)',
                backdropFilter: 'blur(24px)',
                border: '1px solid rgba(168, 131, 255, 0.3)',
                borderRadius: '12px',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.6)',
                zIndex: 50,
                maxHeight: '320px',
                overflowY: 'auto'
              }}>
                <input
                  type="text"
                  value={searchFrom}
                  onChange={(e) => setSearchFrom(e.target.value)}
                  placeholder="Search..."
                  autoFocus
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    marginBottom: '12px',
                    background: 'rgba(255, 255, 255, 0.08)',
                    border: '1px solid rgba(168, 131, 255, 0.3)',
                    borderRadius: '8px',
                    color: 'white',
                    fontSize: '14px'
                  }}
                />
                {loadingAssets ? (
                  <div className="text-center py-4" style={{ color: 'rgba(255, 255, 255, 0.6)' }}>Loading...</div>
                ) : filteredFromCryptos.length === 0 ? (
                  <div className="text-center py-4" style={{ color: 'rgba(255, 255, 255, 0.6)' }}>No currencies found</div>
                ) : (
                  filteredFromCryptos.map((crypto) => (
                    <button
                      key={crypto.code}
                      type="button"
                      onClick={() => {
                        setFromCurrency(crypto.code);
                        setShowFromDropdown(false);
                        setSearchFrom('');
                      }}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        padding: '10px',
                        background: 'transparent',
                        border: 'none',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        transition: 'background 0.2s'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(168, 131, 255, 0.15)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent';
                      }}
                    >
                      <CryptoIcon symbol={crypto.code} size={32} />
                      <div className="ml-3 text-left">
                        <div className="text-white text-sm font-semibold">{crypto.code}</div>
                        <div style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '12px' }}>{crypto.name}</div>
                      </div>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Amount Input */}
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            step="any"
            className="flex-1"
            style={{
              padding: '12px',
              background: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: '12px',
              color: '#e8dbff',
              fontSize: '18px',
              fontWeight: '600',
              outline: 'none',
              transition: 'all 0.3s'
            }}
            onFocus={(e) => {
              e.target.style.borderColor = 'rgba(168, 131, 255, 0.6)';
              e.target.style.background = 'rgba(255, 255, 255, 0.12)';
            }}
            onBlur={(e) => {
              e.target.style.borderColor = 'rgba(255, 255, 255, 0.15)';
              e.target.style.background = 'rgba(255, 255, 255, 0.08)';
            }}
          />
        </div>
        {/* USD Equivalent */}
        {amount && parseFloat(amount) > 0 && usdPrices[fromCurrency] && (
          <div className="mt-2 text-sm" style={{ color: '#a883ff' }}>
            ≈ {formatUSD(parseFloat(amount), fromCurrency)}
          </div>
        )}
      </div>

      {/* Swap Direction Arrow */}
      <div className="flex justify-center my-6">
        <button
          onClick={swapCurrencies}
          style={{
            width: '48px',
            height: '48px',
            borderRadius: '50%',
            background: 'rgba(255, 255, 255, 0.08)',
            border: '1px solid rgba(168, 131, 255, 0.3)',
            color: '#a883ff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(168, 131, 255, 0.2)';
            e.currentTarget.style.borderColor = 'rgba(168, 131, 255, 0.6)';
            e.currentTarget.style.transform = 'rotate(180deg)';
            e.currentTarget.style.boxShadow = '0 0 30px rgba(168, 131, 255, 0.5)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
            e.currentTarget.style.borderColor = 'rgba(168, 131, 255, 0.3)';
            e.currentTarget.style.transform = 'rotate(0deg)';
            e.currentTarget.style.boxShadow = 'none';
          }}
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
          </svg>
        </button>
      </div>

      {/* TO Section */}
      <div className="mb-6">
        <label className="block text-sm font-semibold mb-3" style={{ color: '#b8a6ff' }}>
          You Receive {quoting && <span className="text-xs">(calculating...)</span>}
        </label>
        <div className="flex items-center gap-3">
          {/* Token Icon & Selector */}
          <div className="relative" style={{ width: '200px' }}>
            <button
              type="button"
              onClick={() => setShowToDropdown(!showToDropdown)}
              disabled={loadingAssets}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 16px',
                background: 'rgba(255, 255, 255, 0.08)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '12px',
                color: 'white',
                fontWeight: '600',
                cursor: loadingAssets ? 'not-allowed' : 'pointer',
                transition: 'all 0.3s',
                opacity: loadingAssets ? 0.5 : 1
              }}
              onMouseEnter={(e) => {
                if (!loadingAssets) {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.12)';
                  e.currentTarget.style.borderColor = 'rgba(168, 131, 255, 0.5)';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
                e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.15)';
              }}
            >
              <CryptoIcon symbol={toCurrency} size={28} />
              <span className="flex-1 text-left">{toCurrency}</span>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {showToDropdown && (
              <div style={{
                position: 'absolute',
                top: 'calc(100% + 8px)',
                left: 0,
                right: 0,
                padding: '12px',
                background: 'rgba(13, 11, 20, 0.98)',
                backdropFilter: 'blur(24px)',
                border: '1px solid rgba(168, 131, 255, 0.3)',
                borderRadius: '12px',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.6)',
                zIndex: 50,
                maxHeight: '320px',
                overflowY: 'auto'
              }}>
                <input
                  type="text"
                  value={searchTo}
                  onChange={(e) => setSearchTo(e.target.value)}
                  placeholder="Search..."
                  autoFocus
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    marginBottom: '12px',
                    background: 'rgba(255, 255, 255, 0.08)',
                    border: '1px solid rgba(168, 131, 255, 0.3)',
                    borderRadius: '8px',
                    color: 'white',
                    fontSize: '14px'
                  }}
                />
                {loadingAssets ? (
                  <div className="text-center py-4" style={{ color: 'rgba(255, 255, 255, 0.6)' }}>Loading...</div>
                ) : filteredToCryptos.length === 0 ? (
                  <div className="text-center py-4" style={{ color: 'rgba(255, 255, 255, 0.6)' }}>No currencies found</div>
                ) : (
                  filteredToCryptos.map((crypto) => (
                    <button
                      key={crypto.code}
                      type="button"
                      onClick={() => {
                        setToCurrency(crypto.code);
                        setShowToDropdown(false);
                        setSearchTo('');
                      }}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        padding: '10px',
                        background: 'transparent',
                        border: 'none',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        transition: 'background 0.2s'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(168, 131, 255, 0.15)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent';
                      }}
                    >
                      <CryptoIcon symbol={crypto.code} size={32} />
                      <div className="ml-3 text-left">
                        <div className="text-white text-sm font-semibold">{crypto.code}</div>
                        <div style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '12px' }}>{crypto.name}</div>
                      </div>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Estimated Amount */}
          <input
            type="text"
            value={quote ? quote.estimated_output.toFixed(8) : '~'}
            readOnly
            className="flex-1"
            style={{
              padding: '12px',
              background: 'rgba(20, 241, 149, 0.08)',
              border: '1px solid rgba(20, 241, 149, 0.2)',
              borderRadius: '12px',
              color: '#14F195',
              fontSize: '18px',
              fontWeight: '600',
              cursor: 'not-allowed'
            }}
          />
        </div>
        {/* USD Equivalent for output */}
        {quote && usdPrices[toCurrency] && (
          <div className="mt-2 text-sm" style={{ color: '#14F195' }}>
            ≈ {formatUSD(quote.estimated_output, toCurrency)}
          </div>
        )}
      </div>

      {/* Quote Details */}
      {quote && (
        <div className="mb-6" style={{
          padding: '16px',
          background: 'rgba(168, 131, 255, 0.08)',
          border: '1px solid rgba(168, 131, 255, 0.2)',
          borderRadius: '12px'
        }}>
          {timeRemaining > 0 && (
            <div className="flex items-center justify-between text-sm mb-3 pb-3" style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
              <span className="flex items-center gap-2" style={{ color: '#b8a6ff' }}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Quote expires in
              </span>
              <span className="font-bold" style={{ color: '#d7c6ff' }}>
                {Math.floor(timeRemaining / 60)}:{(timeRemaining % 60).toString().padStart(2, '0')}
              </span>
            </div>
          )}
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span style={{ color: 'rgba(255, 255, 255, 0.6)' }}>Exchange Rate</span>
              <span className="font-semibold" style={{ color: '#e8dbff' }}>1 {quote.from_asset} = {quote.exchange_rate.toFixed(8)} {quote.to_asset}</span>
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'rgba(255, 255, 255, 0.6)' }}>Platform Fee</span>
              <span style={{ color: '#e8dbff' }}>{quote.platform_fee_percent}% ({quote.platform_fee_units.toFixed(8)} {quote.from_asset})</span>
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'rgba(255, 255, 255, 0.6)' }}>Network Fee</span>
              <span style={{ color: '#e8dbff' }}>{quote.changenow_network_fee.toFixed(8)} {quote.to_asset}</span>
            </div>
          </div>
        </div>
      )}

      {/* Destination Address */}
      <div className="mb-6">
        <label className="block text-sm font-semibold mb-3" style={{ color: '#b8a6ff' }}>
          Recipient {toCurrency} Address <span style={{ color: '#ff4444' }}>*</span>
        </label>
        <input
          type="text"
          value={toAddress}
          onChange={(e) => setToAddress(e.target.value)}
          placeholder={`Enter ${toCurrency} address`}
          style={{
            width: '100%',
            padding: '12px',
            background: 'rgba(255, 255, 255, 0.08)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: '12px',
            color: '#e8dbff',
            fontFamily: 'monospace',
            fontSize: '14px',
            outline: 'none',
            transition: 'all 0.3s'
          }}
          onFocus={(e) => {
            e.target.style.borderColor = 'rgba(168, 131, 255, 0.6)';
            e.target.style.background = 'rgba(255, 255, 255, 0.12)';
          }}
          onBlur={(e) => {
            e.target.style.borderColor = 'rgba(255, 255, 255, 0.15)';
            e.target.style.background = 'rgba(255, 255, 255, 0.08)';
          }}
        />
      </div>

      {/* Advanced Options */}
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="flex items-center gap-2 text-sm font-semibold mb-4 transition-colors"
        style={{ color: '#a883ff' }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = '#d7c6ff';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = '#a883ff';
        }}
      >
        <svg className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        Advanced Options
      </button>

      {showAdvanced && (
        <div className="space-y-4 mb-6" style={{
          padding: '16px',
          background: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '12px'
        }}>
          <div>
            <label className="block text-sm font-semibold mb-3" style={{ color: '#b8a6ff' }}>Refund Address (Optional)</label>
            <input
              type="text"
              value={refundAddress}
              onChange={(e) => setRefundAddress(e.target.value)}
              placeholder={`Enter ${fromCurrency} address for refunds`}
              style={{
                width: '100%',
                padding: '12px',
                background: 'rgba(255, 255, 255, 0.08)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '12px',
                color: '#e8dbff',
                fontFamily: 'monospace',
                fontSize: '14px',
                outline: 'none'
              }}
            />
            <p className="text-xs mt-2" style={{ color: 'rgba(255, 255, 255, 0.5)' }}>If swap fails, funds will be refunded to this address.</p>
          </div>
          <div>
            <label className="block text-sm font-semibold mb-3" style={{ color: '#b8a6ff' }}>Slippage Tolerance: {slippageTolerance}%</label>
            <input
              type="range"
              min="0.1"
              max="5"
              step="0.1"
              value={slippageTolerance}
              onChange={(e) => setSlippageTolerance(e.target.value)}
              className="w-full"
              style={{
                WebkitAppearance: 'none',
                appearance: 'none',
                height: '6px',
                background: 'rgba(255, 255, 255, 0.1)',
                borderRadius: '3px',
                outline: 'none'
              }}
            />
            <div className="flex justify-between text-xs mt-1" style={{ color: 'rgba(255, 255, 255, 0.5)' }}>
              <span>0.1% (Low)</span>
              <span>5% (High)</span>
            </div>
          </div>
        </div>
      )}

      {/* Execute Button */}
      <button
        onClick={handleSwap}
        disabled={loading || !amount || !toAddress || !quote}
        style={{
          width: '100%',
          padding: '16px',
          background: loading || !amount || !toAddress || !quote ? 'rgba(255, 255, 255, 0.1)' : 'linear-gradient(90deg, #d7c6ff, #a883ff, #6d35ff)',
          border: 'none',
          borderRadius: '12px',
          color: 'white',
          fontSize: '16px',
          fontWeight: '700',
          cursor: loading || !amount || !toAddress || !quote ? 'not-allowed' : 'pointer',
          transition: 'all 0.4s',
          boxShadow: loading || !amount || !toAddress || !quote ? 'none' : '0 0 30px rgba(168, 131, 255, 0.4)',
          opacity: loading || !amount || !toAddress || !quote ? 0.5 : 1
        }}
        onMouseEnter={(e) => {
          if (!loading && amount && toAddress && quote) {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = '0 0 40px rgba(168, 131, 255, 0.6)';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.boxShadow = loading || !amount || !toAddress || !quote ? 'none' : '0 0 30px rgba(168, 131, 255, 0.4)';
        }}
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Processing...
          </span>
        ) : 'Execute Swap'}
      </button>
    </div>
  );

  if (authLoading) {
    return renderLoadingSpinner();
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'radial-gradient(circle at top right, #1c1528 0%, #0d0b14 70%)',
      position: 'relative'
    }}>
      <Toaster position="top-right" />
      <Navbar />

      {!isAuthenticated && (
        <div style={{
          position: 'fixed',
          inset: 0,
          zIndex: 40,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '16px',
          background: 'rgba(0, 0, 0, 0.7)',
          backdropFilter: 'blur(12px)'
        }}>
          <div style={{
            background: 'rgba(13, 11, 20, 0.95)',
            backdropFilter: 'blur(24px)',
            border: '1px solid rgba(168, 131, 255, 0.3)',
            borderRadius: '24px',
            padding: '48px',
            maxWidth: '400px',
            width: '100%',
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.6), 0 0 60px rgba(168, 131, 255, 0.3)',
            textAlign: 'center'
          }}>
            <div style={{
              width: '80px',
              height: '80px',
              margin: '0 auto 24px',
              borderRadius: '20px',
              background: 'linear-gradient(135deg, #a883ff, #6d35ff)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">Sign in to swap</h2>
            <p className="mb-6" style={{ color: 'rgba(255, 255, 255, 0.6)' }}>Connect your Discord account to continue</p>
            <button
              onClick={() => setShowLoginModal(true)}
              style={{
                width: '100%',
                padding: '16px',
                background: 'linear-gradient(90deg, #d7c6ff, #a883ff, #6d35ff)',
                border: 'none',
                borderRadius: '12px',
                color: 'white',
                fontSize: '16px',
                fontWeight: '700',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '12px',
                boxShadow: '0 0 30px rgba(168, 131, 255, 0.4)'
              }}
            >
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M20.317 4.37a19.791 19.791 0 00-4.885-1.515.074.074 0 00-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 00-5.487 0 12.64 12.64 0 00-.617-1.25.077.077 0 00-.079-.037A19.736 19.736 0 003.677 4.37a.07.07 0 00-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 00.031.057 19.9 19.9 0 005.993 3.03.078.078 0 00.084-.028 14.09 14.09 0 001.226-1.994.076.076 0 00-.041-.106 13.107 13.107 0 01-1.872-.892.077.077 0 01-.008-.128 10.2 10.2 0 00.372-.292.074.074 0 01.077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 01.078.01c.12.098.246.198.373.292a.077.077 0 01-.006.127 12.299 12.299 0 01-1.873.892.077.077 0 00-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 00.084.028 19.839 19.839 0 006.002-3.03.077.077 0 00.032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 00-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
              </svg>
              Login with Discord
            </button>
            <p className="text-xs mt-6" style={{ color: 'rgba(255, 255, 255, 0.4)' }}>Secure authentication powered by Discord</p>
          </div>
        </div>
      )}

      <div className={`container mx-auto px-4 md:px-6 pt-24 md:pt-32 pb-12 md:pb-20 ${!isAuthenticated ? 'blur-sm pointer-events-none' : ''}`}>
        <div className="mb-8 md:mb-12 text-center">
          <h1 style={{
            fontSize: 'clamp(2rem, 5vw, 3.75rem)',
            fontWeight: 'bold',
            background: 'linear-gradient(90deg, #d7c6ff, #a883ff, #6d35ff)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            marginBottom: '12px'
          }}>Instant Swap</h1>
          <p style={{ fontSize: '18px', color: '#b8a6ff' }}>Exchange cryptocurrencies at the best rates</p>
        </div>

        {activeSwap ? renderPaymentScreen() : renderSwapForm()}
      </div>

      <LoginModal isOpen={showLoginModal} onClose={() => setShowLoginModal(false)} />
    </div>
  );
}
