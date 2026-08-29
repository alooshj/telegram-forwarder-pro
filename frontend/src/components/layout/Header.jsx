import React, { useState } from 'react';
import { useUser, useClerk } from '@clerk/clerk-react';
import { TeleTipsLogo } from '../brand/TeleTipsLogo';
import { TeleTipsMark } from '../brand/TeleTipsMark';

export const Header = ({
  isEngineRunning = true,
  connectedSessionsCount = 1,
  activeTab = 'overview',
  onTabChange = () => {},
  currentLang = 'ar',
  onToggleLang = () => {},
  sidebarCollapsed = false,
  onToggleSidebar = () => {}
}) => {
  const { user, isSignedIn } = useUser();
  const { signOut, openUserProfile, openSignIn } = useClerk();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const isRTL = currentLang === 'ar';

  return (
    <header className="bg-surface-900/90 backdrop-blur-xl border-b border-glass-border sticky top-0 z-40 h-16 flex items-center px-4 sm:px-6 lg:px-8 transition-colors duration-200">
      <div className="w-full flex items-center justify-between">
        
        {/* Right Area (in RTL): Brand Logo & Sidebar Toggle */}
        <div className="flex items-center space-x-3 sm:space-x-4 rtl:space-x-reverse">
          {/* Sidebar Mobile/Desktop Toggle */}
          <button
            onClick={onToggleSidebar}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-surface-800/80 border border-transparent hover:border-glass-border transition-all active:scale-95"
            title="Toggle Sidebar"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>

          {/* Brand Logo Component */}
          <div 
            onClick={() => onTabChange('overview')}
            className="cursor-pointer flex items-center group py-1 select-none"
          >
            <TeleTipsLogo className="h-7 sm:h-8 w-auto hidden sm:block" />
            <TeleTipsMark className="h-8 w-8 sm:hidden" />
          </div>

          <div className="h-5 w-px bg-slate-800 hidden md:block" />

          {/* Subscriptions / VIP Quick Pill */}
          <button
            onClick={() => onTabChange('pricing')}
            className="hidden sm:flex items-center space-x-1.5 rtl:space-x-reverse px-3 py-1.5 rounded-xl text-xs font-bold bg-indigo-600/80 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 border border-indigo-400/30 transition-all hover:scale-[1.02] active:scale-95"
          >
            <span>👑</span>
            <span>{currentLang === 'ar' ? 'الخطط والاشتراكات' : 'Plans & VIP'}</span>
            <span className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse" />
          </button>
        </div>

        {/* Left Area (in RTL): Live Status Indicators & User Profile */}
        <div className="flex items-center space-x-2.5 sm:space-x-3.5 rtl:space-x-reverse">
          
          {/* Live Engine Status Indicator */}
          <div className="flex items-center space-x-2 rtl:space-x-reverse bg-surface-850/80 border border-glass-border px-3 py-1.5 rounded-xl text-xs font-medium text-slate-200">
            <span 
              className={`w-2 h-2 rounded-full ${
                isEngineRunning ? 'bg-accent-emerald animate-radar-ping' : 'bg-accent-danger'
              }`} 
            />
            <span className="hidden sm:inline font-mono">
              {isEngineRunning
                ? (currentLang === 'ar' ? 'المحرك نشط' : 'Engine: Active')
                : (currentLang === 'ar' ? 'المحرك متوقف' : 'Engine: Stopped')
              }
            </span>
          </div>

          {/* Connected Sessions Pill */}
          <div 
            onClick={() => onTabChange('sessions')}
            className="hidden md:flex items-center space-x-1.5 rtl:space-x-reverse bg-cyan-950/40 border border-accent-cyan/30 text-cyan-300 px-2.5 py-1.5 rounded-xl text-xs font-mono cursor-pointer hover:border-accent-cyan/60 transition"
            title="Active Sessions"
          >
            <svg className="w-3.5 h-3.5 text-accent-cyan" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"></path>
            </svg>
            <span>{connectedSessionsCount} {currentLang === 'ar' ? 'جلسات متصلة' : 'Sessions'}</span>
          </div>

          {/* Language Switcher */}
          <button
            onClick={onToggleLang}
            className="px-2.5 py-1.5 rounded-xl text-xs font-mono font-bold bg-surface-800 text-slate-300 hover:text-white border border-glass-border transition-all active:scale-95"
            title="Switch Language"
          >
            {currentLang === 'ar' ? 'EN' : 'عربي'}
          </button>

          {/* User Profile / Auth Button */}
          <div className="relative">
            {isSignedIn ? (
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center space-x-2 rtl:space-x-reverse p-1 pl-2.5 rounded-xl bg-surface-850 hover:bg-surface-800 border border-glass-border transition active:scale-95"
              >
                <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-accent-indigo to-accent-cyan flex items-center justify-center text-white font-bold text-xs uppercase shadow-sm">
                  {user?.firstName ? user.firstName[0] : (user?.primaryEmailAddress?.emailAddress?.[0] || 'U')}
                </div>
                <span className="hidden lg:inline text-xs font-bold text-white max-w-[100px] truncate">
                  {user?.firstName || user?.username || user?.primaryEmailAddress?.emailAddress?.split('@')[0]}
                </span>
                <svg className="w-3.5 h-3.5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M6 9l6 6 6-6"></path>
                </svg>
              </button>
            ) : (
              <button
                onClick={() => openSignIn()}
                className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-gradient-to-r from-accent-indigo to-accent-cyan text-white shadow-md shadow-accent-cyan/20 transition-all hover:scale-[1.02] active:scale-95"
              >
                {currentLang === 'ar' ? 'تسجيل الدخول' : 'Sign In'}
              </button>
            )}

            {/* User Dropdown Menu */}
            {dropdownOpen && isSignedIn && (
              <div 
                className="absolute left-0 rtl:left-auto rtl:right-0 mt-2 w-56 rounded-2xl bg-surface-900 border border-glass-border shadow-2xl p-2 z-50 text-xs space-y-1 animate-fade-in"
                onMouseLeave={() => setDropdownOpen(false)}
              >
                <div className="p-2 border-b border-glass-border/60">
                  <p className="font-bold text-white truncate">{user?.fullName || 'Client'}</p>
                  <p className="text-[11px] font-mono text-slate-400 truncate">{user?.primaryEmailAddress?.emailAddress}</p>
                </div>

                <button
                  onClick={() => { setDropdownOpen(false); openUserProfile(); }}
                  className="w-full flex items-center space-x-2 rtl:space-x-reverse p-2 rounded-xl hover:bg-surface-800 text-slate-300 hover:text-white transition"
                >
                  <svg className="w-4 h-4 text-accent-cyan" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="7" r="4"></circle>
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                  </svg>
                  <span>{currentLang === 'ar' ? 'إعدادات الحساب' : 'Account Profile'}</span>
                </button>

                <button
                  onClick={() => { setDropdownOpen(false); signOut(); }}
                  className="w-full flex items-center space-x-2 rtl:space-x-reverse p-2 rounded-xl hover:bg-rose-500/10 text-accent-danger hover:text-rose-300 transition font-bold"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                    <polyline points="16 17 21 12 16 7"></polyline>
                    <line x1="21" y1="12" x2="9" y2="12"></line>
                  </svg>
                  <span>{currentLang === 'ar' ? 'تسجيل الخروج' : 'Sign Out'}</span>
                </button>
              </div>
            )}
          </div>
        </div>

      </div>
    </header>
  );
};

export default Header;
