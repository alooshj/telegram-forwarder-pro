import React from 'react';
import { TeleTipsLogo } from '../brand/TeleTipsLogo';
import { TeleTipsMark } from '../brand/TeleTipsMark';

export const Sidebar = ({
  activeTab = 'overview',
  onTabChange = () => {},
  collapsed = false,
  onToggleCollapse = () => {},
  currentLang = 'ar',
  userRole = 'client'
}) => {
  const isRTL = currentLang === 'ar';
  const isSuperAdmin = userRole === 'super_admin' || userRole === 'admin';

  const navItems = [
    {
      id: 'overview',
      labelAr: 'نظرة عامة',
      labelEn: 'Overview',
      icon: (
        <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="7" height="9"></rect>
          <rect x="14" y="3" width="7" height="5"></rect>
          <rect x="14" y="12" width="7" height="9"></rect>
          <rect x="3" y="16" width="7" height="5"></rect>
        </svg>
      )
    },
    {
      id: 'pipelines',
      labelAr: 'استوديو القنوات والتوجيه',
      labelEn: 'Pipelines Studio',
      badge: 'PRO',
      badgeColor: 'bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30',
      icon: (
        <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="17 1 21 5 17 9"></polyline>
          <path d="M3 11V9a4 4 0 0 1 4-4h14"></path>
          <polyline points="7 23 3 19 7 15"></polyline>
          <path d="M21 13v2a4 4 0 0 1-4 4H3"></path>
        </svg>
      )
    },
    {
      id: 'sessions',
      labelAr: 'إدارة الجلسات السحابية',
      labelEn: 'Session Manager',
      icon: (
        <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"></path>
        </svg>
      )
    },
    {
      id: 'logs',
      labelAr: 'شاشة السجلات اللحظية',
      labelEn: 'Live Logs Terminal',
      icon: (
        <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
        </svg>
      )
    },
    {
      id: 'blacklist',
      labelAr: 'القائمة السوداء والفلترة',
      labelEn: 'Blacklist & Filters',
      icon: (
        <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line>
        </svg>
      )
    },
    {
      id: 'pricing',
      labelAr: 'الباقات والاشتراكات',
      labelEn: 'Billing & Payments',
      badge: 'VIP',
      badgeColor: 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30',
      icon: (
        <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
        </svg>
      )
    }
  ];

  if (isSuperAdmin) {
    navItems.push({
      id: 'admin',
      labelAr: 'لوحة الإدارة والأعضاء',
      labelEn: 'Admin Control',
      badge: 'ROOT',
      badgeColor: 'bg-rose-500/20 text-rose-300 border border-rose-500/30',
      icon: (
        <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
        </svg>
      )
    });
  }

  return (
    <aside 
      className={`hidden md:flex flex-col bg-surface-900/95 backdrop-blur-2xl border-l rtl:border-l-0 rtl:border-r border-glass-border transition-all duration-300 z-30 ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-glass-border">
        {!collapsed ? (
          <div 
            onClick={() => onTabChange('overview')}
            className="cursor-pointer group py-1 flex items-center select-none"
          >
            <TeleTipsLogo className="h-7 w-auto" />
          </div>
        ) : (
          <div 
            onClick={() => onTabChange('overview')}
            className="cursor-pointer mx-auto py-1"
          >
            <TeleTipsMark className="h-8 w-8" />
          </div>
        )}

        <button
          onClick={onToggleCollapse}
          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-surface-800 transition active:scale-95"
          title={collapsed ? "Expand Sidebar" : "Collapse Sidebar"}
        >
          <svg 
            className={`w-4 h-4 transition-transform duration-200 ${
              isRTL ? (collapsed ? '' : 'rotate-180') : (collapsed ? 'rotate-180' : '')
            }`} 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2"
          >
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
        </button>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto custom-scrollbar">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center rounded-xl p-3 text-xs font-semibold transition-all group relative ${
                isActive
                  ? 'bg-gradient-to-r from-accent-indigo via-indigo-600 to-indigo-700 text-white shadow-lg shadow-indigo-500/25'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-surface-800/70'
              } ${collapsed ? 'justify-center' : 'justify-between'}`}
              title={collapsed ? (isRTL ? item.labelAr : item.labelEn) : undefined}
            >
              <div className="flex items-center space-x-3 rtl:space-x-reverse min-w-0">
                <span className={`${isActive ? 'text-white' : 'text-slate-400 group-hover:text-accent-cyan transition-colors'}`}>
                  {item.icon}
                </span>
                {!collapsed && (
                  <span className="truncate">
                    {isRTL ? item.labelAr : item.labelEn}
                  </span>
                )}
              </div>

              {!collapsed && item.badge && (
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md ${item.badgeColor}`}>
                  {item.badge}
                </span>
              )}

              {/* Active Indicator Glow Pip */}
              {isActive && (
                <span className="absolute right-0 rtl:right-auto rtl:left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-accent-cyan rounded-full shadow-glow-cyan" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer System Status Box */}
      {!collapsed && (
        <div className="p-3 m-3 rounded-2xl bg-surface-950/80 border border-glass-border space-y-2">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400 font-mono">TeleTips Node v2.5</span>
            <span className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse" />
          </div>
          <p className="text-[10px] text-slate-500 leading-tight">
            {isRTL ? 'محرك التوجيه الذكي الآمن متصل بالسحابة' : 'Cloud message routing pipeline connected'}
          </p>
        </div>
      )}
    </aside>
  );
};

export default Sidebar;
