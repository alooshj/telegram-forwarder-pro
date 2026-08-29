import React from 'react';

export const MobileNav = ({
  activeTab = 'overview',
  onTabChange = () => {},
  currentLang = 'ar'
}) => {
  const isRTL = currentLang === 'ar';

  const items = [
    {
      id: 'overview',
      labelAr: 'الرئيسية',
      labelEn: 'Overview',
      icon: (
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="7" height="9"></rect>
          <rect x="14" y="3" width="7" height="5"></rect>
          <rect x="14" y="12" width="7" height="9"></rect>
          <rect x="3" y="16" width="7" height="5"></rect>
        </svg>
      )
    },
    {
      id: 'pipelines',
      labelAr: 'القواعد',
      labelEn: 'Pipelines',
      icon: (
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="17 1 21 5 17 9"></polyline>
          <path d="M3 11V9a4 4 0 0 1 4-4h14"></path>
          <polyline points="7 23 3 19 7 15"></polyline>
          <path d="M21 13v2a4 4 0 0 1-4 4H3"></path>
        </svg>
      )
    },
    {
      id: 'sessions',
      labelAr: 'الجلسات',
      labelEn: 'Sessions',
      icon: (
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"></path>
        </svg>
      )
    },
    {
      id: 'logs',
      labelAr: 'السجلات',
      labelEn: 'Logs',
      icon: (
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
        </svg>
      )
    },
    {
      id: 'pricing',
      labelAr: 'الترقية',
      labelEn: 'Plans',
      icon: (
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
        </svg>
      )
    }
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-surface-900/95 backdrop-blur-2xl border-t border-glass-border px-2 py-2 flex items-center justify-around">
      {items.map((item) => {
        const isActive = activeTab === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            className={`flex flex-col items-center justify-center py-1 px-3 rounded-xl transition-all duration-200 ${
              isActive
                ? 'text-accent-cyan bg-cyan-500/10 scale-105'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <div className="relative">
              {item.icon}
              {isActive && (
                <span className="absolute -top-1 -right-1 w-1.5 h-1.5 rounded-full bg-accent-cyan shadow-glow-cyan" />
              )}
            </div>
            <span className="text-[10px] font-bold mt-1 tracking-tight">
              {isRTL ? item.labelAr : item.labelEn}
            </span>
          </button>
        );
      })}
    </nav>
  );
};

export default MobileNav;
