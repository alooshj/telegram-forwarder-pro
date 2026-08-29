import React, { useState, useEffect } from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { MobileNav } from './MobileNav';

export const DashboardLayout = ({
  children,
  activeTab = 'overview',
  onTabChange = () => {},
  isEngineRunning = true,
  connectedSessionsCount = 1,
  userRole = 'client'
}) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [currentLang, setCurrentLang] = useState(
    () => localStorage.getItem('tp_lang') || 'ar'
  );

  const toggleLanguage = () => {
    const nextLang = currentLang === 'ar' ? 'en' : 'ar';
    setCurrentLang(nextLang);
    localStorage.setItem('tp_lang', nextLang);
  };

  useEffect(() => {
    document.documentElement.lang = currentLang;
    document.documentElement.dir = currentLang === 'ar' ? 'rtl' : 'ltr';
  }, [currentLang]);

  return (
    <div className={`min-h-screen bg-background text-slate-100 flex flex-row ${currentLang === 'ar' ? 'font-sans' : 'font-sans'}`}>
      
      {/* 1. Desktop Collapsible Sidebar */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={onTabChange}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        currentLang={currentLang}
        userRole={userRole}
      />

      {/* 2. Main Content Wrapper */}
      <div className="flex-1 flex flex-col min-w-0 pb-16 md:pb-0">
        
        {/* Top Navbar Header */}
        <Header
          isEngineRunning={isEngineRunning}
          connectedSessionsCount={connectedSessionsCount}
          activeTab={activeTab}
          onTabChange={onTabChange}
          currentLang={currentLang}
          onToggleLang={toggleLanguage}
          sidebarCollapsed={sidebarCollapsed}
          onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
        />

        {/* Dynamic Page Content Viewport with Glass Container */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto animate-fade-in overflow-y-auto custom-scrollbar">
          {children}
        </main>
      </div>

      {/* 3. Fixed Mobile Bottom Navigation */}
      <MobileNav
        activeTab={activeTab}
        onTabChange={onTabChange}
        currentLang={currentLang}
      />
    </div>
  );
};

export default DashboardLayout;
