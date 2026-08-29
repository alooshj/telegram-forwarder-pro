import React, { useState } from 'react';

export const LiveLogsTerminal = ({
  logs = [
    { time: '12:04:12.184', level: 'INFO', pipeline: '#01', msg: 'Forwarded post #4928 to -100192837482 in 142ms | Intact Album (3 Photos)' },
    { time: '12:04:14.920', level: 'INFO', pipeline: '#02', msg: 'Scrubbed 2 URLs and replaced branding footer in 38ms' },
    { time: '12:04:18.012', level: 'WARN', pipeline: '#01', msg: 'FloodWait buffer auto-paused for 2s (safety window)' },
    { time: '12:04:22.440', level: 'INFO', pipeline: '#03', msg: 'Direct text match replaced: @old_brand -> @teletips' }
  ],
  onClear = () => {},
  currentLang = 'ar'
}) => {
  const isRTL = currentLang === 'ar';
  const [filterLevel, setFilterLevel] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [isPaused, setIsPaused] = useState(false);

  const filteredLogs = logs.filter(l => {
    if (filterLevel !== 'ALL' && l.level !== filterLevel) return false;
    if (searchQuery && !JSON.stringify(l).toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      
      {/* Top Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-card p-5 rounded-2xl">
        <div className="flex items-center space-x-2.5 rtl:space-x-reverse">
          <span className="w-2.5 h-2.5 rounded-full bg-accent-emerald animate-pulse" />
          <div>
            <h2 className="text-lg sm:text-xl font-black text-white font-mono">
              Live Routing CLI Terminal
            </h2>
            <p className="text-xs text-slate-400">
              {isRTL ? 'بث حي وفوري لكافة عمليات التوجيه وتعديل المحتوى عبر الـ WebSocket' : 'Real-time execution stream of all routing, transforms, and album grouping.'}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center flex-wrap gap-2">
          {/* Pause / Resume */}
          <button
            onClick={() => setIsPaused(!isPaused)}
            className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold transition ${
              isPaused ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'bg-surface-800 text-slate-300 hover:text-white'
            }`}
          >
            {isPaused ? '▶ Resume Feed' : '⏸ Pause Feed'}
          </button>

          {/* Clear Logs */}
          <button
            onClick={onClear}
            className="px-3 py-1.5 rounded-xl text-xs font-mono font-bold bg-surface-800 text-slate-400 hover:text-rose-300 transition"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="glass-card p-3 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center space-x-1 rtl:space-x-reverse">
          {['ALL', 'INFO', 'WARN', 'ERROR'].map(lvl => (
            <button
              key={lvl}
              onClick={() => setFilterLevel(lvl)}
              className={`px-3 py-1 rounded-lg font-mono font-bold transition ${
                filterLevel === lvl
                  ? 'bg-accent-cyan text-slate-950 shadow-glow-cyan'
                  : 'bg-surface-850 text-slate-400 hover:text-white'
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>

        <div className="relative max-w-xs w-full">
          <input
            type="text"
            placeholder="Search logs pattern..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-surface-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-accent-cyan font-mono"
          />
        </div>
      </div>

      {/* Terminal Display */}
      <div className="rounded-2xl bg-surface-950 border border-slate-800 p-4 font-mono text-xs text-slate-300 shadow-2xl h-[520px] overflow-y-auto custom-scrollbar space-y-2">
        {filteredLogs.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-600 italic">
            No routing events matching criteria...
          </div>
        ) : (
          filteredLogs.map((l, i) => (
            <div key={i} className="flex items-start space-x-2 rtl:space-x-reverse leading-relaxed hover:bg-surface-900/60 p-1 rounded transition">
              <span className="text-slate-500 select-none">[{l.time}]</span>
              <span className={`font-bold select-none ${
                l.level === 'ERROR' ? 'text-accent-danger' : l.level === 'WARN' ? 'text-accent-warning' : 'text-accent-cyan'
              }`}>
                [{l.level}]
              </span>
              {l.pipeline && <span className="text-indigo-400 font-bold">{l.pipeline}:</span>}
              <span className="text-slate-200">{l.msg}</span>
            </div>
          ))
        )}
      </div>

    </div>
  );
};

export default LiveLogsTerminal;
