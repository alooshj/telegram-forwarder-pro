import React from 'react';

export const OverviewView = ({
  stats = { totalForwarded: 1420, activeRules: 6, avgLatency: '185ms', albumsCollected: 48, scrubbedUrls: 920 },
  rules = [],
  logs = [],
  onToggleRule = () => {},
  onNavigate = () => {},
  isEngineRunning = true,
  currentLang = 'ar'
}) => {
  const isRTL = currentLang === 'ar';

  return (
    <div className="space-y-6">
      
      {/* Top Banner: Engine & Session Status Card */}
      <div className="glass-card rounded-2xl p-5 sm:p-6 bg-gradient-to-r from-surface-900 via-surface-850 to-indigo-950/40 relative overflow-hidden">
        <div className="absolute -top-12 -left-12 w-48 h-48 bg-accent-cyan/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 relative z-10">
          <div className="space-y-1">
            <div className="flex items-center space-x-2.5 rtl:space-x-reverse">
              <span className="text-xl sm:text-2xl font-black text-white">
                {isRTL ? 'لوحة تحكم TeleTips Pro السحابية' : 'TeleTips Pro Cloud Command Center'}
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30 animate-pulse">
                {isEngineRunning ? (isRTL ? 'المحرك نشط' : 'LIVE ONLINE') : (isRTL ? 'متوقف' : 'PAUSED')}
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400">
              {isRTL 
                ? 'توجيه آلي لحظي فائق السرعة لقنوات ومجموعات تليجرام مع تخطي القيود وتعديل المحتوى.'
                : 'Sub-second real-time Telegram channel & group forwarding pipeline with smart filter engines.'
              }
            </p>
          </div>

          <div className="flex items-center space-x-2 rtl:space-x-reverse">
            <button
              onClick={() => onNavigate('pipelines')}
              className="px-4 py-2.5 bg-gradient-to-r from-accent-indigo to-accent-cyan hover:opacity-90 text-white font-bold text-xs rounded-xl shadow-lg shadow-accent-cyan/20 transition-all hover:scale-[1.02] active:scale-95 flex items-center space-x-1.5 rtl:space-x-reverse"
            >
              <span>⚡</span>
              <span>{isRTL ? 'إضافة مسار توجيه جديد' : 'Create New Pipeline'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* 4 KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        
        {/* KPI 1: Forwarded Messages */}
        <div className="glass-card rounded-2xl p-5 space-y-2 relative overflow-hidden group">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">
              {isRTL ? 'الرسائل المحولة اليوم' : 'Messages Forwarded'}
            </span>
            <div className="w-8 h-8 rounded-xl bg-accent-cyan/10 text-accent-cyan flex items-center justify-center font-bold">
              ⚡
            </div>
          </div>
          <div className="text-3xl font-black text-white font-mono tracking-tight group-hover:text-accent-cyan transition-colors">
            {stats.totalForwarded.toLocaleString()}
          </div>
          <p className="text-[11px] text-accent-emerald flex items-center space-x-1 rtl:space-x-reverse">
            <span>↑ 99.98%</span>
            <span className="text-slate-500 font-normal">{isRTL ? 'معدل النجاح' : 'Success Rate'}</span>
          </p>
        </div>

        {/* KPI 2: Routing Latency */}
        <div className="glass-card rounded-2xl p-5 space-y-2 relative overflow-hidden group">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">
              {isRTL ? 'سرعة التوجيه اللحظي' : 'Avg Routing Latency'}
            </span>
            <div className="w-8 h-8 rounded-xl bg-accent-emerald/10 text-accent-emerald flex items-center justify-center font-bold">
              ⏱️
            </div>
          </div>
          <div className="text-3xl font-black text-accent-emerald font-mono tracking-tight">
            {stats.avgLatency}
          </div>
          <p className="text-[11px] text-slate-400">
            {isRTL ? 'معالجة فورية فائقة السرعة' : 'Sub-second real-time execution'}
          </p>
        </div>

        {/* KPI 3: Albums Collected */}
        <div className="glass-card rounded-2xl p-5 space-y-2 relative overflow-hidden group">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">
              {isRTL ? 'ألبومات تم تجميعها' : 'Albums Grouped'}
            </span>
            <div className="w-8 h-8 rounded-xl bg-accent-indigo/10 text-accent-indigo flex items-center justify-center font-bold">
              📁
            </div>
          </div>
          <div className="text-3xl font-black text-white font-mono tracking-tight group-hover:text-indigo-400 transition-colors">
            {stats.albumsCollected}
          </div>
          <p className="text-[11px] text-slate-400">
            {isRTL ? 'بواسطة AlbumCollector' : 'Preserved by AlbumCollector'}
          </p>
        </div>

        {/* KPI 4: Scrubbed URLs */}
        <div className="glass-card rounded-2xl p-5 space-y-2 relative overflow-hidden group">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">
              {isRTL ? 'روابط وإعلانات تم تنظيفها' : 'Scrubbed URLs & Ads'}
            </span>
            <div className="w-8 h-8 rounded-xl bg-accent-purple/10 text-accent-purple flex items-center justify-center font-bold">
              🧹
            </div>
          </div>
          <div className="text-3xl font-black text-white font-mono tracking-tight group-hover:text-purple-300 transition-colors">
            {stats.scrubbedUrls}
          </div>
          <p className="text-[11px] text-slate-400">
            {isRTL ? 'تعديل وحذف فوري' : 'Automated Content Cleanup'}
          </p>
        </div>

      </div>

      {/* Grid: Active Pipelines & Mini Live Terminal */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Cols: Active Pipelines Widget */}
        <div className="lg:col-span-2 glass-card rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-glass-border pb-3">
            <div className="flex items-center space-x-2 rtl:space-x-reverse">
              <span className="text-sm font-bold text-white">
                {isRTL ? 'مسارات التوجيه النشطة' : 'Active Forwarding Pipelines'}
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-surface-800 text-slate-300">
                {stats.activeRules}
              </span>
            </div>
            <button
              onClick={() => onNavigate('pipelines')}
              className="text-xs text-accent-cyan hover:underline font-semibold"
            >
              {isRTL ? 'إدارة جميع القواعد ←' : 'Manage All →'}
            </button>
          </div>

          <div className="space-y-3">
            {rules.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-xs">
                {isRTL ? 'لا توجد مسارات مضافة بعد. اضغط زر "إضافة مسار" للبدء.' : 'No active forwarding pipelines yet. Click "Create New Pipeline" to get started.'}
              </div>
            ) : (
              rules.slice(0, 4).map((r, i) => (
                <div key={r.id || i} className="p-3 rounded-xl bg-surface-850/60 border border-glass-border flex items-center justify-between gap-3 hover:border-accent-cyan/30 transition">
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center space-x-2 rtl:space-x-reverse">
                      <span className="font-bold text-white text-xs truncate">{r.name || `Pipeline #${i+1}`}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                        {r.source_id} ➔ {Array.isArray(r.target_ids) ? r.target_ids.join(', ') : r.target_ids}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 truncate">
                      {r.replace_text ? `Transforms: "${r.search_text || 'All'}" ➔ "${r.replace_text}"` : 'Direct forwarding mode'}
                    </p>
                  </div>

                  <div className="flex items-center space-x-2 rtl:space-x-reverse flex-shrink-0">
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={r.active !== false}
                        onChange={() => onToggleRule(r.id)}
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] rtl:after:left-auto rtl:after:right-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-accent-emerald"></div>
                    </label>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right 1 Col: Mini Live Logs Terminal */}
        <div className="glass-card rounded-2xl p-5 space-y-3 flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-glass-border pb-3">
            <div className="flex items-center space-x-2 rtl:space-x-reverse">
              <span className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse" />
              <span className="text-sm font-bold text-white">
                {isRTL ? 'رادار السجلات اللحظي' : 'Live Stream Terminal'}
              </span>
            </div>
            <button
              onClick={() => onNavigate('logs')}
              className="text-xs text-accent-cyan hover:underline font-semibold"
            >
              {isRTL ? 'الشاشة الكاملة' : 'Full CLI'}
            </button>
          </div>

          <div className="bg-surface-950/90 rounded-xl p-3 font-mono text-[11px] text-slate-300 h-64 overflow-y-auto custom-scrollbar space-y-1.5 border border-slate-800">
            {logs.length === 0 ? (
              <p className="text-slate-600 italic">Waiting for incoming messages...</p>
            ) : (
              logs.slice(-8).map((l, i) => (
                <div key={i} className="leading-snug">
                  <span className="text-slate-500">[{l.time || 'NOW'}] </span>
                  <span className={l.level === 'ERROR' ? 'text-accent-danger font-bold' : l.level === 'WARN' ? 'text-accent-warning' : 'text-accent-cyan'}>
                    [{l.level || 'INFO'}]
                  </span>{' '}
                  <span className="text-slate-200">{l.msg || l.message}</span>
                </div>
              ))
            )}
          </div>

          <div className="pt-2 flex items-center justify-between text-[10px] text-slate-500 font-mono">
            <span>Stream: WebSocket Live</span>
            <span className="text-accent-emerald">● Connected (0ms)</span>
          </div>
        </div>

      </div>

    </div>
  );
};

export default OverviewView;
