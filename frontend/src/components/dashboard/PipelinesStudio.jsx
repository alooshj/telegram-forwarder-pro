import React, { useState } from 'react';

export const PipelinesStudio = ({
  rules = [],
  onSaveRule = () => {},
  onDeleteRule = () => {},
  currentLang = 'ar'
}) => {
  const isRTL = currentLang === 'ar';

  const [ruleName, setRuleName] = useState('');
  const [sourceChannel, setSourceChannel] = useState('');
  const [targetChannels, setTargetChannels] = useState('');
  const [searchText, setSearchText] = useState('');
  const [replaceText, setReplaceText] = useState('');
  const [urlScrubber, setUrlScrubber] = useState(true);
  const [albumCollector, setAlbumCollector] = useState(true);
  const [includeKeywords, setIncludeKeywords] = useState('');
  const [excludeKeywords, setExcludeKeywords] = useState('');

  // Sample message for interactive Before/After preview
  const [sampleMessage, setSampleMessage] = useState(
    "🔥 Breaking News: Join our channel @old_channel for daily tips! https://t.me/old_channel Check this out #news"
  );

  // Live transformed output calculation
  const getTransformedPreview = () => {
    let text = sampleMessage;
    if (searchText && replaceText !== undefined) {
      try {
        text = text.replace(new RegExp(searchText, 'gi'), replaceText);
      } catch {
        text = text.split(searchText).join(replaceText);
      }
    }
    if (urlScrubber) {
      text = text.replace(/https?:\/\/[^\s]+/g, '').replace(/@[a-zA-Z0-9_]+/g, '');
    }
    return text.trim();
  };

  return (
    <div className="space-y-6">
      
      {/* Studio Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-card p-5 rounded-2xl">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-white">
            {isRTL ? 'استوديو مسارات وقواعد التوجيه الذكية' : 'Pipelines Studio & Rules Engine'}
          </h2>
          <p className="text-xs sm:text-sm text-slate-400">
            {isRTL 
              ? 'صمم مسار التوجيه بين القنوات وفلاتر الكلمات واستبدال الروابط وتجميع الألبومات.' 
              : 'Architect routing pipelines, content scrubber rules, regex transforms, and media grouping.'
            }
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left 7 Cols: Rule Configuration Studio */}
        <div className="lg:col-span-7 space-y-5">
          
          <div className="glass-card rounded-2xl p-6 space-y-5">
            <h3 className="text-sm font-bold text-white flex items-center space-x-2 rtl:space-x-reverse border-b border-glass-border pb-3">
              <span>🛠️</span>
              <span>{isRTL ? '1. إعدادات المسار والقنوات (Source ➔ Targets)' : '1. Pipeline Source & Target Channels'}</span>
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  {isRTL ? 'اسم المسار التوضيحي' : 'Pipeline Identifier Name'}
                </label>
                <input
                  type="text"
                  placeholder={isRTL ? 'مثال: مسار أخبار العملات والصفقات' : 'e.g. VIP Signals Forwarder'}
                  value={ruleName}
                  onChange={(e) => setRuleName(e.target.value)}
                  className="w-full bg-surface-950 border border-slate-700 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-accent-cyan"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    {isRTL ? 'القناة المصدر (Source Channel ID / User)' : 'Source Channel (ID / User)'}
                  </label>
                  <input
                    type="text"
                    placeholder="-1001234567890"
                    dir="ltr"
                    value={sourceChannel}
                    onChange={(e) => setSourceChannel(e.target.value)}
                    className="w-full bg-surface-950 border border-slate-700 rounded-xl px-4 py-2.5 text-xs font-mono text-cyan-300 placeholder-slate-600 focus:outline-none focus:border-accent-cyan"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    {isRTL ? 'القنوات الهدف (Target Channels IDs)' : 'Target Channels (Comma-separated IDs)'}
                  </label>
                  <input
                    type="text"
                    placeholder="-1009876543210, -100555555"
                    dir="ltr"
                    value={targetChannels}
                    onChange={(e) => setTargetChannels(e.target.value)}
                    className="w-full bg-surface-950 border border-slate-700 rounded-xl px-4 py-2.5 text-xs font-mono text-emerald-300 placeholder-slate-600 focus:outline-none focus:border-accent-emerald"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Smart Rules & Filters Engine */}
          <div className="glass-card rounded-2xl p-6 space-y-5">
            <h3 className="text-sm font-bold text-white flex items-center space-x-2 rtl:space-x-reverse border-b border-glass-border pb-3">
              <span>🧠</span>
              <span>{isRTL ? '2. محرك الفلترة وتعديل المحتوى (Smart Engine)' : '2. Smart Transformation & Filters Engine'}</span>
            </h3>

            {/* Smart Feature Toggles */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              
              {/* URL Scrubber */}
              <div className="p-3.5 rounded-xl bg-surface-950/60 border border-glass-border flex items-center justify-between">
                <div>
                  <span className="font-bold text-white text-xs block">
                    {isRTL ? 'تنظيف الروابط والمنشن (URL Scrubber)' : 'URL & Mention Scrubber'}
                  </span>
                  <span className="text-[11px] text-slate-400">
                    {isRTL ? 'حذف روابط t.me والمعرفات @' : 'Strip source links & usernames'}
                  </span>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={urlScrubber}
                    onChange={(e) => setUrlScrubber(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] rtl:after:left-auto rtl:after:right-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-accent-cyan"></div>
                </label>
              </div>

              {/* Album Collector */}
              <div className="p-3.5 rounded-xl bg-surface-950/60 border border-glass-border flex items-center justify-between">
                <div>
                  <span className="font-bold text-white text-xs block">
                    {isRTL ? 'تجميع الألبومات (AlbumCollector)' : 'AlbumCollector (Grouped Photos)'}
                  </span>
                  <span className="text-[11px] text-slate-400">
                    {isRTL ? 'تجميع منشورات الصور المتعددة كألبوم' : 'Forward multi-photos as intact album'}
                  </span>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={albumCollector}
                    onChange={(e) => setAlbumCollector(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] rtl:after:left-auto rtl:after:right-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-accent-emerald"></div>
                </label>
              </div>

            </div>

            {/* Keyword Replace & Search */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  {isRTL ? 'نص البحث أو الكلمة القديمة' : 'Search Text / Pattern'}
                </label>
                <input
                  type="text"
                  placeholder="@old_channel"
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                  className="w-full bg-surface-950 border border-slate-700 rounded-xl px-4 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-accent-cyan"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  {isRTL ? 'النص البديل / حقوق قناتك' : 'Replacement / Custom Branding'}
                </label>
                <input
                  type="text"
                  placeholder="@my_official_channel"
                  value={replaceText}
                  onChange={(e) => setReplaceText(e.target.value)}
                  className="w-full bg-surface-950 border border-slate-700 rounded-xl px-4 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-accent-cyan"
                />
              </div>
            </div>

            <button
              type="button"
              className="w-full py-3 bg-gradient-to-r from-accent-indigo via-indigo-600 to-accent-cyan hover:opacity-90 text-white font-bold text-xs rounded-xl shadow-lg shadow-accent-cyan/20 transition hover:scale-[1.01] active:scale-95"
            >
              {isRTL ? '⚡ حفظ وتفعيل مسار التوجيه الآن' : '⚡ Save & Deploy Pipeline'}
            </button>
          </div>

        </div>

        {/* Right 5 Cols: Dynamic Live "Before & After" Interactive Simulator */}
        <div className="lg:col-span-5 space-y-5">
          
          <div className="glass-card rounded-2xl p-6 space-y-4 sticky top-20">
            <div className="flex items-center justify-between border-b border-glass-border pb-3">
              <div className="flex items-center space-x-2 rtl:space-x-reverse">
                <span className="text-xs font-bold text-accent-cyan uppercase tracking-wider">
                  {isRTL ? 'المحاكي اللحظي المباشر' : 'Live Transformation Preview'}
                </span>
              </div>
              <span className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse" />
            </div>

            {/* Input message simulation */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-400 mb-1">
                {isRTL ? 'رسالة تجريبية من المصدر (Original Input):' : 'Sample Incoming Message:'}
              </label>
              <textarea
                rows={3}
                value={sampleMessage}
                onChange={(e) => setSampleMessage(e.target.value)}
                className="w-full bg-surface-950/90 border border-slate-800 rounded-xl p-3 text-xs text-slate-300 font-mono focus:outline-none focus:border-slate-600"
              />
            </div>

            {/* Output transformed card */}
            <div>
              <label className="block text-[11px] font-semibold text-accent-emerald mb-1">
                {isRTL ? 'النتيجة بعد تطبيق القواعد (Live Processed Output):' : 'Processed Live Output:'}
              </label>
              <div className="p-4 rounded-xl bg-gradient-to-b from-surface-950 to-surface-900 border border-accent-emerald/30 text-xs font-mono text-white shadow-inner space-y-2 min-h-[90px]">
                <p className="whitespace-pre-wrap leading-relaxed">
                  {getTransformedPreview() || <span className="text-slate-600 italic">No content</span>}
                </p>
                {replaceText && (
                  <div className="pt-2 border-t border-slate-800/80 text-[10px] text-accent-cyan font-bold">
                    ✓ Custom branding appended
                  </div>
                )}
              </div>
            </div>

            <div className="p-3 rounded-xl bg-surface-950/60 border border-glass-border text-[11px] text-slate-400 space-y-1">
              <p className="font-bold text-slate-300">💡 {isRTL ? 'ملاحظة التوجيه الآمن:' : 'Pro Routing Tip:'}</p>
              <p>{isRTL ? 'يتم تطبيق قواعد الحذف والفلترة في الذاكرة بزمن استجابة أقل من 50ms.' : 'Transformation rules execute in-memory with sub-50ms latency before forwarding.'}</p>
            </div>

          </div>

        </div>

      </div>

    </div>
  );
};

export default PipelinesStudio;
