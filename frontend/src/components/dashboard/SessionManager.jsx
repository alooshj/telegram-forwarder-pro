import React, { useState } from 'react';

export const SessionManager = ({
  sessions = [
    { id: 'sess_1', phone: '+9665*****123', name: 'Main VIP Forwarder', status: 'connected', dc: 'DC4 (Europe)', ping: '42ms', lastActive: 'Just now' },
    { id: 'sess_2', phone: '+1202*****884', name: 'Secondary Backup Bot', status: 'floodwait', waitSeconds: 45, dc: 'DC2 (US)', ping: '88ms', lastActive: '2m ago' }
  ],
  onConnectNew = () => {},
  onDisconnect = () => {},
  currentLang = 'ar'
}) => {
  const isRTL = currentLang === 'ar';
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [connectStep, setConnectStep] = useState(1);
  const [phoneNumber, setPhoneNumber] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [password2FA, setPassword2FA] = useState('');

  return (
    <div className="space-y-6">
      
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 glass-card p-5 rounded-2xl">
        <div className="space-y-1">
          <div className="flex items-center space-x-2.5 rtl:space-x-reverse">
            <h2 className="text-xl sm:text-2xl font-black text-white">
              {isRTL ? 'إدارة جلسات تليجرام السحابية المشفرة' : 'Encrypted Telegram Session Manager'}
            </h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30">
              AES-256 Cloud
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-400">
            {isRTL 
              ? 'اتصال سحابي آمن ومشفر بحسابات Userbot لتخطي قيود البوتات الرسمية والتوجيه من القنوات المحمية.'
              : 'End-to-end encrypted Telethon Userbot sessions bypassing restricted forwarding limitations.'
            }
          </p>
        </div>

        <button
          onClick={() => { setShowConnectModal(true); setConnectStep(1); }}
          className="px-4 py-2.5 bg-gradient-to-r from-accent-indigo to-accent-cyan hover:opacity-90 text-white font-bold text-xs rounded-xl shadow-lg shadow-accent-cyan/20 transition hover:scale-[1.02] active:scale-95 flex items-center space-x-1.5 rtl:space-x-reverse flex-shrink-0"
        >
          <span>📱</span>
          <span>{isRTL ? 'ربط حساب تليجرام جديد' : 'Connect New Session'}</span>
        </button>
      </div>

      {/* Sessions Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {sessions.map((sess) => {
          const isConnected = sess.status === 'connected';
          const isFloodWait = sess.status === 'floodwait';

          return (
            <div key={sess.id} className="glass-card rounded-2xl p-5 space-y-4 relative overflow-hidden group">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2.5 rtl:space-x-reverse">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-accent-indigo to-accent-cyan text-white flex items-center justify-center font-bold text-sm shadow-md">
                    TG
                  </div>
                  <div>
                    <h4 className="font-bold text-white text-xs">{sess.name}</h4>
                    <p className="text-[11px] font-mono text-slate-400">{sess.phone}</p>
                  </div>
                </div>

                {/* Status Badge */}
                {isConnected && (
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-accent-emerald/15 text-accent-emerald border border-accent-emerald/30 flex items-center space-x-1 rtl:space-x-reverse">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent-emerald animate-pulse" />
                    <span>Active</span>
                  </span>
                )}
                {isFloodWait && (
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center space-x-1 rtl:space-x-reverse animate-pulse">
                    <span>⏳ FloodWait ({sess.waitSeconds}s)</span>
                  </span>
                )}
                {!isConnected && !isFloodWait && (
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-500/15 text-rose-300 border border-rose-500/30">
                    Offline
                  </span>
                )}
              </div>

              <div className="p-3 rounded-xl bg-surface-950/60 border border-glass-border grid grid-cols-2 gap-2 text-[11px] font-mono text-slate-300">
                <div>
                  <span className="text-slate-500 block">Data Center:</span>
                  <span className="text-slate-200">{sess.dc}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Latency:</span>
                  <span className="text-accent-emerald">{sess.ping}</span>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-glass-border text-xs">
                <span className="text-[10px] text-slate-500">AES-256 Encrypted</span>
                <button
                  onClick={() => onDisconnect(sess.id)}
                  className="text-accent-danger hover:text-rose-300 font-bold transition text-xs"
                >
                  {isRTL ? 'قطع الاتصال' : 'Terminate'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Connect Account Modal */}
      {showConnectModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="glass-card rounded-2xl max-w-md w-full p-6 space-y-5 bg-surface-900 border border-glass-border animate-fade-in">
            <div className="flex items-center justify-between border-b border-glass-border pb-3">
              <div className="flex items-center space-x-2 rtl:space-x-reverse">
                <span className="text-lg">📱</span>
                <h3 className="font-bold text-white text-base">
                  {isRTL ? 'ربط حساب تليجرام (Telegram Web Connect)' : 'Telegram Web Connect'}
                </h3>
              </div>
              <button 
                onClick={() => setShowConnectModal(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg bg-surface-800"
              >
                ✕
              </button>
            </div>

            {connectStep === 1 && (
              <div className="space-y-4">
                <p className="text-xs text-slate-300">
                  {isRTL ? 'أدخل رقم هاتفك الدولي المرتبط بحسابك في تليجرام:' : 'Enter international phone number linked to Telegram:'}
                </p>
                <input
                  type="tel"
                  placeholder="+966501234567"
                  dir="ltr"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  className="w-full bg-surface-950 border border-slate-700 rounded-xl px-4 py-2.5 text-xs font-mono text-cyan-300 placeholder-slate-600 focus:outline-none focus:border-accent-cyan"
                />
                <button
                  type="button"
                  onClick={() => setConnectStep(2)}
                  className="w-full py-2.5 bg-gradient-to-r from-accent-indigo to-accent-cyan text-white font-bold text-xs rounded-xl shadow-md transition"
                >
                  {isRTL ? 'إرسال كود التحقق ➔' : 'Send Verification Code ➔'}
                </button>
              </div>
            )}

            {connectStep === 2 && (
              <div className="space-y-4">
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs text-emerald-300">
                  ✓ {isRTL ? 'تم إرسال كود التحقق الرسمي إلى تطبيق تليجرام الخاص بك.' : 'Verification code sent to your official Telegram app.'}
                </div>
                <input
                  type="text"
                  placeholder="12345"
                  dir="ltr"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  className="w-full bg-surface-950 border border-slate-700 rounded-xl px-4 py-2.5 text-sm font-mono text-center tracking-widest text-emerald-300 focus:outline-none focus:border-accent-emerald"
                />
                <input
                  type="password"
                  placeholder={isRTL ? 'كلمة مرور التحقق بخطوتين 2FA (اختياري)' : '2FA Password (if enabled)'}
                  value={password2FA}
                  onChange={(e) => setPassword2FA(e.target.value)}
                  className="w-full bg-surface-950 border border-slate-700 rounded-xl px-4 py-2 text-xs text-slate-300 focus:outline-none focus:border-accent-cyan"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => setConnectStep(1)}
                    className="w-1/3 py-2.5 bg-surface-800 text-slate-300 font-bold text-xs rounded-xl"
                  >
                    {isRTL ? 'رجوع' : 'Back'}
                  </button>
                  <button
                    onClick={() => setShowConnectModal(false)}
                    className="w-2/3 py-2.5 bg-gradient-to-r from-accent-emerald to-emerald-600 text-slate-950 font-black text-xs rounded-xl shadow-md"
                  >
                    {isRTL ? 'تأكيد وحفظ الجلسة المشفرة' : 'Confirm & Encrypt'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  );
};

export default SessionManager;
