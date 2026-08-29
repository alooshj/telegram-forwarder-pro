/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#0b0f17',
        surface: {
          800: '#1c2536',
          850: '#151c28',
          900: '#0b0f17',
          950: '#06090e',
        },
        card: '#151c28',
        btn: {
          base: '#1c2536',
          hover: '#263248',
          active: '#2a374f',
        },
        neon: {
          cyan: '#00e5ff',
          emerald: '#10b981',
        },
        accent: {
          emerald: '#10B981',
          cyan: '#00e5ff',
          warning: '#F59E0B',
          danger: '#EF4444',
          purple: '#8B5CF6',
          indigo: '#6366F1',
        },
        glass: {
          border: 'rgba(255, 255, 255, 0.08)',
          card: 'rgba(21, 28, 40, 0.85)',
          hover: 'rgba(38, 50, 72, 0.6)',
        }
      },
      fontFamily: {
        sans: ['Tajawal', 'Readex Pro', 'Inter', 'sans-serif'],
        arabic: ['Tajawal', 'Readex Pro', 'sans-serif'],
        tajawal: ['Tajawal', 'sans-serif'],
        mono: ['JetBrains Mono', 'Inter', 'monospace'],
      },
      boxShadow: {
        'glow-cyan': '0 0 20px rgba(0, 229, 255, 0.4)',
        'glow-cyan-lg': '0 0 35px rgba(0, 229, 255, 0.6)',
        'glow-emerald': '0 0 20px rgba(16, 185, 129, 0.4)',
        'glow-emerald-lg': '0 0 35px rgba(16, 185, 129, 0.6)',
        'glow-indigo': '0 0 20px -3px rgba(99, 102, 241, 0.45)',
        'glass-card': '0 10px 30px -10px rgba(0, 0, 0, 0.5)',
      },
      animation: {
        'fade-in': 'fadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'pulse-glow': 'pulseGlow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'radar-ping': 'radarPing 2s cubic-bezier(0, 0, 0.2, 1) infinite',
        'shimmer': 'shimmer 2.5s infinite linear',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(6px) scale(0.995)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        pulseGlow: {
          '0%, 100%': { opacity: '1', filter: 'drop-shadow(0 0 8px rgba(16, 185, 129, 0.6))' },
          '50%': { opacity: '0.75', filter: 'drop-shadow(0 0 2px rgba(16, 185, 129, 0.2))' },
        },
        radarPing: {
          '0%': { transform: 'scale(0.95)', boxShadow: '0 0 0 0 rgba(16, 185, 129, 0.7)' },
          '70%': { transform: 'scale(1.05)', boxShadow: '0 0 0 7px rgba(16, 185, 129, 0)' },
          '100%': { transform: 'scale(0.95)', boxShadow: '0 0 0 0 rgba(16, 185, 129, 0)' },
        },
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        }
      }
    },
  },
  plugins: [],
}
