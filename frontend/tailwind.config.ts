import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Afroo Brand Colors - Futuristic Neon
        primary: {
          light: '#bfa3ff',
          DEFAULT: '#7c6df6',
          dark: '#6d35ff',
          glow: '#8f60ff',
        },
        arc: {
          light: '#b6a2f2',
          DEFAULT: '#8a79ff',
          dark: '#7b42f7',
        },
        success: '#2ECC71',
        error: '#E74C3C',
        warning: '#F39C12',
        info: '#3498DB',

        // Text colors
        foreground: '#ffffff',

        // Crypto Colors
        crypto: {
          btc: '#F7931A',
          eth: '#627EEA',
          ltc: '#345D9D',
          sol: '#14F195',
          usdt: '#26A17B',
          usdc: '#2775CA',
        },

        // Dark theme with neon bg
        dark: {
          bg: '#0e0d14',
          'bg-light': '#16131f',
          card: '#1a1825',
          hover: '#211e2f',
          border: '#2d2a3f',
        },
      },
      backgroundImage: {
        'gradient-primary': 'linear-gradient(135deg, #bfa3ff 0%, #7c6df6 50%, #6d35ff 100%)',
        'gradient-arc': 'linear-gradient(135deg, #b6a2f2 0%, #8a79ff 50%, #7b42f7 100%)',
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-bg': 'linear-gradient(180deg, #0e0d14 0%, #16131f 100%)',
      },
      boxShadow: {
        'neon': '0 0 20px rgba(143, 96, 255, 0.15)',
        'neon-lg': '0 0 40px rgba(143, 96, 255, 0.2)',
        'inner-glow': 'inset 0 1px 0 rgba(255, 255, 255, 0.1)',
      },
      backdropBlur: {
        'glass': '12px',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in',
        'slide-up': 'slideUp 0.5s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
export default config
