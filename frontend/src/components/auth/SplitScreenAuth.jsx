import React, { useState } from 'react';
import { SignIn, SignUp, useAuth, useClerk } from '@clerk/clerk-react';
import { Navigate, Link } from 'react-router-dom';
import { teletipsClerkAppearance } from '../../theme/clerkTheme';

export const SplitScreenAuth = ({ mode = 'signin' }) => {
  const { isLoaded, isSignedIn } = useAuth();
  const clerk = useClerk();
  const [oauthLoading, setOauthLoading] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  if (!isLoaded) {
    return (
      <div className="min-h-screen bg-[#0b0f17] flex items-center justify-center">
        <div className="relative flex items-center justify-center">
          <div className="w-12 h-12 rounded-full border-2 border-[#1c2536] border-t-[#00e5ff] animate-spin" />
          <div className="absolute w-6 h-6 rounded-full bg-[#00e5ff]/20 blur-md animate-pulse" />
        </div>
      </div>
    );
  }

  if (isSignedIn) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleOAuth = async (strategy) => {
    try {
      setOauthLoading(strategy);
      setErrorMessage('');
      const targetMethod = mode === 'signup' ? clerk.client.signUp : clerk.client.signIn;
      if (targetMethod && typeof targetMethod.authenticateWithRedirect === 'function') {
        await targetMethod.authenticateWithRedirect({
          strategy,
          redirectUrl: '/dashboard',
          redirectUrlComplete: '/dashboard',
        });
      }
    } catch (err) {
      console.error('OAuth initiation error:', err);
      setErrorMessage('تعذر بدء تسجيل الدخول، يرجى المحاولة مرة أخرى.');
      setOauthLoading(null);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#0b0f17] text-white flex flex-col md:flex-row antialiased selection:bg-[#00e5ff]/30 selection:text-[#00e5ff] font-['Tajawal',sans-serif]" dir="rtl">
      
      {/* =========================================================================
          HERO & BRANDING SIDE (Right column on RTL desktop, hidden on mobile)
          ========================================================================= */}
      <div className="hidden md:flex md:w-1/2 lg:w-7/12 relative overflow-hidden bg-[#0b0f17] border-l border-white/5 flex-col justify-between p-8 lg:p-14">
        
        {/* Background Cyber Glow & Radial Gradients */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(0,229,255,0.15),rgba(255,255,255,0))]" />
        <div className="absolute -bottom-32 -right-32 w-96 h-96 bg-[#00e5ff]/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/3 -left-20 w-80 h-80 bg-[#10b981]/10 rounded-full blur-3xl pointer-events-none" />

        {/* Ambient Grid Overlay */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:3rem_3rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] pointer-events-none" />

        {/* Brand Header */}
        <div className="relative z-10 flex items-center space-x-3 rtl:space-x-reverse">
          <div className="relative group">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-[#00e5ff] to-[#10b981] rounded-2xl blur opacity-60 group-hover:opacity-100 transition duration-300" />
            <div className="relative p-2.5 bg-[#151c28] rounded-2xl border border-white/10 shadow-xl flex items-center justify-center">
              <img src="/logo.png" alt="TeleTips Pro" className="h-9 w-auto object-contain filter drop-shadow-[0_0_12px_rgba(0,229,255,0.5)]" />
            </div>
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight text-white flex items-center gap-2">
              <span>TeleTips</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-[#00e5ff]/10 text-[#00e5ff] border border-[#00e5ff]/30 font-bold font-mono uppercase tracking-wider">
                PRO 2.0
              </span>
            </h1>
            <p className="text-xs text-slate-400 font-medium">سحابة توجيه وأتمتة منشورات تليجرام الذكية</p>
          </div>
        </div>

        {/* Central Feature Showcase */}
        <div className="relative z-10 my-auto py-10 space-y-6 max-w-lg">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#1c2536]/80 border border-[#00e5ff]/20 text-[#00e5ff] text-xs font-bold shadow-[0_0_15px_rgba(0,229,255,0.15)]">
            <span className="w-2 h-2 rounded-full bg-[#00e5ff] animate-ping" />
            <span>نظام الأتمتة المتقدم 24/7 بدون انقطاع</span>
          </div>

          <h2 className="text-3xl lg:text-4xl font-extrabold leading-tight text-white tracking-tight">
            تحكم كامل في مسارات <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#00e5ff] via-cyan-200 to-[#10b981]">التوجيه المباشر</span> بدقة فائقة
          </h2>

          <p className="text-sm text-slate-300 leading-relaxed">
            منصة سحابية متطورة تتيح لك توجيه المنشورات والألبومات فورياً بين القنوات والمجموعات مع تنظيف الروابط، وتطبيق فلاتر الكلمات المتقدمة، وتشفير الجلسات بأعلى معايير الأمان.
          </p>

          {/* Feature Grid Chips */}
          <div className="grid grid-cols-2 gap-3 pt-2">
            <div className="p-3.5 bg-[#151c28]/90 rounded-2xl border border-white/5 hover:border-[#00e5ff]/30 transition group shadow-lg">
              <div className="w-8 h-8 rounded-xl bg-[#00e5ff]/10 text-[#00e5ff] flex items-center justify-center text-base mb-2 group-hover:scale-110 transition">
                ⚡
              </div>
              <h4 className="text-xs font-bold text-white mb-0.5">سرعة فائقة &lt; 1 ثانية</h4>
              <p className="text-[11px] text-slate-400 leading-normal">توجيه فوري لحظة النشر بدون أي تأخير.</p>
            </div>

            <div className="p-3.5 bg-[#151c28]/90 rounded-2xl border border-white/5 hover:border-[#10b981]/30 transition group shadow-lg">
              <div className="w-8 h-8 rounded-xl bg-[#10b981]/10 text-[#10b981] flex items-center justify-center text-base mb-2 group-hover:scale-110 transition">
                🛡️
              </div>
              <h4 className="text-xs font-bold text-white mb-0.5">عزل سحابي متعدد</h4>
              <p className="text-[11px] text-slate-400 leading-normal">عزل كامل لبيانات وسجلات وقواعد كل مشترك.</p>
            </div>

            <div className="p-3.5 bg-[#151c28]/90 rounded-2xl border border-white/5 hover:border-purple-500/30 transition group shadow-lg">
              <div className="w-8 h-8 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center text-base mb-2 group-hover:scale-110 transition">
                ⚙️
              </div>
              <h4 className="text-xs font-bold text-white mb-0.5">استبدال وفلترة النصوص</h4>
              <p className="text-[11px] text-slate-400 leading-normal">حذف الروابط، استبدال المعرفات، وتخصيص الفوتر.</p>
            </div>

            <div className="p-3.5 bg-[#151c28]/90 rounded-2xl border border-white/5 hover:border-amber-500/30 transition group shadow-lg">
              <div className="w-8 h-8 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center text-base mb-2 group-hover:scale-110 transition">
                🔒
              </div>
              <h4 className="text-xs font-bold text-white mb-0.5">تشفير AES-256</h4>
              <p className="text-[11px] text-slate-400 leading-normal">حماية جلسات تليجرام بتشفير عسكري مشفر.</p>
            </div>
          </div>
        </div>

        {/* Footer Meta */}
        <div className="relative z-10 flex items-center justify-between text-xs text-slate-500 border-t border-white/5 pt-4">
          <span>&copy; 2026 TeleTips Pro. جميع الحقوق محفوظة.</span>
          <span className="font-mono text-[#00e5ff]/70 text-[11px]">v2.4.0 • Enterprise Cloud</span>
        </div>
      </div>

      {/* =========================================================================
          AUTH FORM SIDE (Centered card with Social Login & Email Authentication)
          ========================================================================= */}
      <div className="w-full md:w-1/2 lg:w-5/12 flex items-center justify-center p-4 sm:p-8 lg:p-12 relative">
        
        {/* Subtle mobile neon background */}
        <div className="absolute top-1/4 -right-16 w-64 h-64 bg-[#00e5ff]/10 rounded-full blur-3xl pointer-events-none md:hidden" />

        <div className="w-full max-w-md space-y-6 z-10">
          
          {/* Mobile Brand Logo Banner */}
          <div className="flex md:hidden flex-col items-center text-center space-y-2 mb-2">
            <div className="p-2.5 bg-[#151c28] rounded-2xl border border-[#00e5ff]/30 shadow-xl shadow-cyan-950/40">
              <img src="/logo.png" alt="TeleTips Pro" className="h-10 w-auto object-contain filter drop-shadow-[0_0_12px_rgba(0,229,255,0.4)]" />
            </div>
            <h1 className="text-lg font-black text-white">TeleTips Pro</h1>
            <p className="text-xs text-slate-400">سحابة توجيه وأتمتة منشورات تليجرام</p>
          </div>

          {/* Glassmorphism Auth Card */}
          <div className="bg-[#151c28]/95 backdrop-blur-xl border border-white/10 rounded-3xl p-6 sm:p-8 shadow-[0_20px_50px_rgba(0,0,0,0.8),0_0_30px_rgba(0,229,255,0.1)] space-y-6">
            
            {/* Form Title & Switcher */}
            <div className="text-center space-y-1.5 border-b border-white/5 pb-4">
              <h3 className="text-xl font-extrabold text-white">
                {mode === 'signup' ? 'إنشاء حساب جديد' : 'تسجيل الدخول إلى حسابك'}
              </h3>
              <p className="text-xs text-slate-400">
                {mode === 'signup' 
                  ? 'انضم إلى أسرع منصة سحابية لأتمتة تليجرام في ثوانٍ' 
                  : 'اختر طريقة الدخول المفضلة لديك للمتابعة فوراً'}
              </p>
            </div>

            {/* Error Notification */}
            {errorMessage && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-semibold flex items-center gap-2 animate-fade-in">
                <span>⚠️</span>
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Fast Social Auth Actions (Google, Discord, Facebook) */}
            <div className="space-y-2.5">
              <span className="text-[11px] font-bold text-slate-400 block text-center uppercase tracking-wider">
                الدخول السريع بحسابات التواصل
              </span>

              <div className="grid grid-cols-3 gap-2.5">
                
                {/* Google OAuth Button */}
                <button
                  type="button"
                  onClick={() => handleOAuth('oauth_google')}
                  disabled={Boolean(oauthLoading)}
                  className="flex items-center justify-center gap-2 py-3 px-3 rounded-xl bg-[#1c2536] hover:bg-[#263248] border border-white/10 hover:border-[#00e5ff]/40 text-white font-bold text-xs transition duration-200 shadow-md hover:shadow-[0_0_15px_rgba(0,229,255,0.2)] disabled:opacity-50 disabled:cursor-not-allowed group focus:outline-none focus:ring-2 focus:ring-[#00e5ff]/50"
                  title="تسجيل الدخول بحساب Google"
                >
                  {oauthLoading === 'oauth_google' ? (
                    <div className="w-4 h-4 rounded-full border-2 border-slate-600 border-t-[#00e5ff] animate-spin" />
                  ) : (
                    <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                    </svg>
                  )}
                  <span className="hidden sm:inline">Google</span>
                </button>

                {/* Discord OAuth Button */}
                <button
                  type="button"
                  onClick={() => handleOAuth('oauth_discord')}
                  disabled={Boolean(oauthLoading)}
                  className="flex items-center justify-center gap-2 py-3 px-3 rounded-xl bg-[#1c2536] hover:bg-[#263248] border border-white/10 hover:border-[#5865F2]/60 text-white font-bold text-xs transition duration-200 shadow-md hover:shadow-[0_0_15px_rgba(88,101,242,0.3)] disabled:opacity-50 disabled:cursor-not-allowed group focus:outline-none focus:ring-2 focus:ring-[#5865F2]/50"
                  title="تسجيل الدخول بحساب Discord"
                >
                  {oauthLoading === 'oauth_discord' ? (
                    <div className="w-4 h-4 rounded-full border-2 border-slate-600 border-t-[#5865F2] animate-spin" />
                  ) : (
                    <svg className="w-4 h-4 text-[#5865F2] flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.893.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
                    </svg>
                  )}
                  <span className="hidden sm:inline">Discord</span>
                </button>

                {/* Facebook OAuth Button */}
                <button
                  type="button"
                  onClick={() => handleOAuth('oauth_facebook')}
                  disabled={Boolean(oauthLoading)}
                  className="flex items-center justify-center gap-2 py-3 px-3 rounded-xl bg-[#1c2536] hover:bg-[#263248] border border-white/10 hover:border-[#1877F2]/60 text-white font-bold text-xs transition duration-200 shadow-md hover:shadow-[0_0_15px_rgba(24,119,242,0.3)] disabled:opacity-50 disabled:cursor-not-allowed group focus:outline-none focus:ring-2 focus:ring-[#1877F2]/50"
                  title="تسجيل الدخول بحساب Facebook"
                >
                  {oauthLoading === 'oauth_facebook' ? (
                    <div className="w-4 h-4 rounded-full border-2 border-slate-600 border-t-[#1877F2] animate-spin" />
                  ) : (
                    <svg className="w-4 h-4 text-[#1877F2] flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
                    </svg>
                  )}
                  <span className="hidden sm:inline">Facebook</span>
                </button>
              </div>
            </div>

            {/* Visual Divider */}
            <div className="relative flex items-center justify-center">
              <div className="border-t border-white/10 w-full" />
              <span className="bg-[#151c28] px-3 text-[11px] text-slate-400 font-semibold uppercase whitespace-nowrap">
                أو بالبريد الإلكتروني
              </span>
              <div className="border-t border-white/10 w-full" />
            </div>

            {/* Clerk Custom Appearance Component */}
            <div className="clerk-embed-wrapper w-full">
              {mode === 'signup' ? (
                <SignUp
                  routing="path"
                  path="/sign-up"
                  signInUrl="/sign-in"
                  forceRedirectUrl="/dashboard"
                  fallbackRedirectUrl="/dashboard"
                  appearance={teletipsClerkAppearance}
                />
              ) : (
                <SignIn
                  routing="path"
                  path="/sign-in"
                  signUpUrl="/sign-up"
                  forceRedirectUrl="/dashboard"
                  fallbackRedirectUrl="/dashboard"
                  appearance={teletipsClerkAppearance}
                />
              )}
            </div>

            {/* Mode Switcher Footer */}
            <div className="text-center pt-2 text-xs text-slate-400">
              {mode === 'signup' ? (
                <p>
                  لديك حساب بالفعل؟{' '}
                  <Link to="/sign-in" className="text-[#00e5ff] font-bold hover:underline transition">
                    تسجيل الدخول
                  </Link>
                </p>
              ) : (
                <p>
                  ليس لديك حساب بعد؟{' '}
                  <Link to="/sign-up" className="text-[#00e5ff] font-bold hover:underline transition">
                    إنشاء حساب جديد
                  </Link>
                </p>
              )}
            </div>
          </div>

          {/* Secure Trust Badge */}
          <div className="flex items-center justify-center gap-2 text-[11px] text-slate-500 font-medium">
            <svg className="w-3.5 h-3.5 text-[#10b981]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span>محمي بتشفير end-to-end وبروتوكول مصادقة Clerk العالمية</span>
          </div>

        </div>
      </div>
    </div>
  );
};

export default SplitScreenAuth;
