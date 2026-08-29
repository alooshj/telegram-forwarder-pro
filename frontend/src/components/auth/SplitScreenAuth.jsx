import React, { useState, useEffect } from 'react';
import { SignIn, SignUp, useAuth, useClerk } from '@clerk/clerk-react';
import { Navigate, Link } from 'react-router-dom';
import { teletipsClerkAppearance } from '../../theme/clerkTheme';

const strings = {
  ar: {
    langBtn: 'English',
    badge: 'سحابة الأتمتة المتقدمة 24/7 نشطة',
    title1: 'تحكم كامل في مسارات ',
    titleHighlight: 'التوجيه المباشر',
    title2: ' بدقة فائقة',
    desc: 'نظام سحابي فائق السرعة والأمان لإدارة ومزامنة القنوات والمجموعات مع تحكم دقيق بفلاتر النصوص وتشفير الجلسات بأعلى المعايير.',
    feat1Title: 'توجيه فوري < 1 ثانية',
    feat1Desc: 'توجيه فوري للمنشورات والألبومات بدون أي تأخير.',
    feat2Title: 'عزل سحابي متعدد',
    feat2Desc: 'عزل مستقل لبيانات وسجلات وقواعد كل مشترك.',
    feat3Title: 'استبدال وفلترة النصوص',
    feat3Desc: 'تنظيف الروابط وتعديل النصوص والمعرفات بذكاء.',
    feat4Title: 'تشفير AES-256',
    feat4Desc: 'حماية وتشفير الجلسات بأعلى المعايير الأمنية.',
    cardSignInTitle: 'تسجيل الدخول إلى TeleTips',
    cardSignUpTitle: 'إنشاء حساب جديد في TeleTips',
    cardSignInSub: 'أهلاً بك مجدداً! تفضل بالدخول لإدارة قنواتك',
    cardSignUpSub: 'ابدأ تجربتك المجانية الآن وأتمت قنواتك بكل سهولة',
    socialHeader: 'المتابعة السريعة بحسابات التواصل',
    orEmail: 'أو بالبريد الإلكتروني',
    haveAccount: 'لديك حساب بالفعل؟',
    signInLink: 'تسجيل الدخول',
    noAccount: 'ليس لديك حساب بعد؟',
    signUpLink: 'إنشاء حساب جديد',
    clerkBadge: 'محمي بتشفير end-to-end وبروتوكول مصادقة Clerk العالمية',
    errOAuth: 'تعذر بدء تسجيل الدخول، يرجى المحاولة مرة أخرى.',
  },
  en: {
    langBtn: 'العربية',
    badge: 'Advanced 24/7 Cloud Automation Active',
    title1: 'Automate Channels with ',
    titleHighlight: 'TeleTips Pro',
    title2: ' Cloud Forwarder',
    desc: 'High-speed secure cloud platform to manage and synchronize channels and groups with precision text filters and top-tier session encryption.',
    feat1Title: 'Instant Forwarding < 1s',
    feat1Desc: 'Instant delivery for posts and media albums with zero latency.',
    feat2Title: 'Multi-Tenant Isolation',
    feat2Desc: 'Isolated storage and pipelines for each subscriber\'s data and rules.',
    feat3Title: 'Text & Link Filtering',
    feat3Desc: 'Clean links, transform mentions, and customize post formats.',
    feat4Title: 'AES-256 Encryption',
    feat4Desc: 'Military-grade encryption for all user credentials and sessions.',
    cardSignInTitle: 'Sign In to TeleTips',
    cardSignUpTitle: 'Create TeleTips Account',
    cardSignInSub: 'Welcome back! Sign in to manage your forwarding routes',
    cardSignUpSub: 'Start your free trial today and automate your channels',
    socialHeader: 'Quick Continue with Social Accounts',
    orEmail: 'Or with Email',
    haveAccount: 'Already have an account?',
    signInLink: 'Sign In',
    noAccount: "Don't have an account?",
    signUpLink: 'Create New Account',
    clerkBadge: 'Secured with end-to-end encryption & global Clerk authentication protocols',
    errOAuth: 'Failed to initiate login, please try again.',
  }
};

export const SplitScreenAuth = ({ mode = 'signin' }) => {
  const { isLoaded, isSignedIn } = useAuth();
  const clerk = useClerk();
  const [oauthLoading, setOauthLoading] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [lang, setLang] = useState(() => localStorage.getItem('tp_lang') || 'ar');

  const t = strings[lang] || strings.ar;

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  }, [lang]);

  const toggleLanguage = () => {
    const nextLang = lang === 'ar' ? 'en' : 'ar';
    setLang(nextLang);
    localStorage.setItem('tp_lang', nextLang);
  };

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
      setErrorMessage(t.errOAuth);
      setOauthLoading(null);
    }
  };

  return (
    <div
      className="min-h-screen w-full bg-[#0b0f17] text-white flex flex-col md:flex-row antialiased selection:bg-[#00e5ff]/30 selection:text-[#00e5ff] font-['Tajawal',sans-serif] relative overflow-hidden"
      dir={lang === 'ar' ? 'rtl' : 'ltr'}
    >
      {/* =========================================================================
          CINEMATIC VIDEO BACKGROUND LAYER (Crystal Clear & Vivid)
          ========================================================================= */}
      <video
        autoPlay
        loop
        muted
        playsInline
        className="absolute inset-0 w-full h-full object-cover z-0 pointer-events-none"
      >
        <source src="/bg-login.mp4" type="video/mp4" />
      </video>

      {/* Ultra-Light Cyberpunk Glass Overlay */}
      <div className="absolute inset-0 bg-black/20 bg-gradient-to-b from-black/45 via-transparent to-black/65 z-0 pointer-events-none" />
      <div className="absolute top-1/4 -right-24 w-96 h-96 bg-[#00e5ff]/10 rounded-full blur-3xl z-0 pointer-events-none" />
      <div className="absolute bottom-1/4 -left-24 w-96 h-96 bg-[#10b981]/10 rounded-full blur-3xl z-0 pointer-events-none" />

      {/* =========================================================================
          HERO & BRANDING SIDE (Right column on RTL desktop, hidden on mobile)
          ========================================================================= */}
      <div className="hidden md:flex md:w-1/2 lg:w-7/12 relative z-10 overflow-hidden flex-col justify-between p-8 lg:p-14">
        
        {/* Floating Language Switcher */}
        <div className="relative z-10 flex items-center justify-end">
          <button
            type="button"
            onClick={toggleLanguage}
            className="px-3.5 py-2 rounded-xl bg-[#151c28]/85 hover:bg-[#1c2536] border border-white/20 hover:border-[#00e5ff]/50 text-slate-100 hover:text-white font-bold text-xs flex items-center gap-2 backdrop-blur-xl shadow-xl transition duration-200 active:scale-95 group focus:outline-none focus:ring-2 focus:ring-[#00e5ff]/40"
          >
            <svg className="w-4 h-4 text-[#00e5ff] group-hover:rotate-12 transition-transform" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="2" y1="12" x2="22" y2="12" />
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
            <span>{t.langBtn}</span>
          </button>
        </div>

        {/* Central Feature Showcase */}
        <div className="relative z-10 my-auto py-10 space-y-6 max-w-lg">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#1c2536]/90 backdrop-blur-xl border border-[#00e5ff]/30 text-[#00e5ff] text-xs font-bold shadow-[0_0_20px_rgba(0,229,255,0.2)]">
            <span className="w-2 h-2 rounded-full bg-[#00e5ff] animate-ping" />
            <span>{t.badge}</span>
          </div>

          <h2 className="text-3xl lg:text-4xl font-extrabold leading-tight text-white tracking-tight drop-shadow-[0_4px_12px_rgba(0,0,0,0.9)]">
            {t.title1}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#00e5ff] via-cyan-200 to-[#10b981]">
              {t.titleHighlight}
            </span>
            {t.title2}
          </h2>

          <p className="text-sm text-slate-200/90 leading-relaxed font-medium drop-shadow-[0_2px_8px_rgba(0,0,0,0.8)]">
            {t.desc}
          </p>

          {/* Feature Grid Chips with Transparent Frosted Glass */}
          <div className="grid grid-cols-2 gap-4 pt-2">
            <div className="p-4 sm:p-5 bg-[#0f172a]/40 hover:bg-[#0f172a]/65 backdrop-blur-2xl rounded-2xl border border-white/20 hover:border-[#00e5ff]/60 shadow-[0_8px_32px_rgba(0,0,0,0.37)] hover:shadow-[0_0_25px_rgba(0,229,255,0.2)] transition-all duration-300 group">
              <div className="w-9 h-9 rounded-xl bg-[#00e5ff]/20 text-[#00e5ff] border border-[#00e5ff]/30 flex items-center justify-center text-lg mb-2.5 group-hover:scale-110 transition duration-200 shadow-[0_0_15px_rgba(0,229,255,0.25)]">
                ⚡
              </div>
              <h4 className="text-xs sm:text-sm font-extrabold text-white mb-1 tracking-wide">{t.feat1Title}</h4>
              <p className="text-[11px] sm:text-xs text-slate-200/90 leading-relaxed">{t.feat1Desc}</p>
            </div>

            <div className="p-4 sm:p-5 bg-[#0f172a]/40 hover:bg-[#0f172a]/65 backdrop-blur-2xl rounded-2xl border border-white/20 hover:border-[#10b981]/60 shadow-[0_8px_32px_rgba(0,0,0,0.37)] hover:shadow-[0_0_25px_rgba(16,185,129,0.2)] transition-all duration-300 group">
              <div className="w-9 h-9 rounded-xl bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/30 flex items-center justify-center text-lg mb-2.5 group-hover:scale-110 transition duration-200 shadow-[0_0_15px_rgba(16,185,129,0.25)]">
                🛡️
              </div>
              <h4 className="text-xs sm:text-sm font-extrabold text-white mb-1 tracking-wide">{t.feat2Title}</h4>
              <p className="text-[11px] sm:text-xs text-slate-200/90 leading-relaxed">{t.feat2Desc}</p>
            </div>

            <div className="p-4 sm:p-5 bg-[#0f172a]/40 hover:bg-[#0f172a]/65 backdrop-blur-2xl rounded-2xl border border-white/20 hover:border-purple-400/60 shadow-[0_8px_32px_rgba(0,0,0,0.37)] hover:shadow-[0_0_25px_rgba(168,85,247,0.2)] transition-all duration-300 group">
              <div className="w-9 h-9 rounded-xl bg-purple-500/20 text-purple-300 border border-purple-500/30 flex items-center justify-center text-lg mb-2.5 group-hover:scale-110 transition duration-200 shadow-[0_0_15px_rgba(168,85,247,0.25)]">
                ⚙️
              </div>
              <h4 className="text-xs sm:text-sm font-extrabold text-white mb-1 tracking-wide">{t.feat3Title}</h4>
              <p className="text-[11px] sm:text-xs text-slate-200/90 leading-relaxed">{t.feat3Desc}</p>
            </div>

            <div className="p-4 sm:p-5 bg-[#0f172a]/40 hover:bg-[#0f172a]/65 backdrop-blur-2xl rounded-2xl border border-white/20 hover:border-amber-400/60 shadow-[0_8px_32px_rgba(0,0,0,0.37)] hover:shadow-[0_0_25px_rgba(251,191,36,0.2)] transition-all duration-300 group">
              <div className="w-9 h-9 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center justify-center text-lg mb-2.5 group-hover:scale-110 transition duration-200 shadow-[0_0_15px_rgba(251,191,36,0.25)]">
                🔒
              </div>
              <h4 className="text-xs sm:text-sm font-extrabold text-white mb-1 tracking-wide">{t.feat4Title}</h4>
              <p className="text-[11px] sm:text-xs text-slate-200/90 leading-relaxed">{t.feat4Desc}</p>
            </div>
          </div>
        </div>

        {/* Footer Note */}
        <div className="relative z-10 flex items-center justify-between text-xs text-slate-400 font-medium">
          <span>TeleTips Pro &copy; 2026 &bull; Userbot & Cloud Routing</span>
          <span className="text-[#00e5ff] font-mono">v2.0.0-SECURED</span>
        </div>
      </div>

      {/* =========================================================================
          AUTH FORM SIDE (Lateral Glassmorphism Panel)
          ========================================================================= */}
      <div className="w-full md:w-1/2 lg:w-5/12 relative z-10 flex items-center justify-center p-4 sm:p-8 lg:p-12 overflow-y-auto">
        
        {/* Mobile Top Bar */}
        <div className="md:hidden absolute top-4 left-4 right-4 flex items-center justify-end z-20">
          <button
            type="button"
            onClick={toggleLanguage}
            className="px-3 py-1.5 rounded-lg bg-[#151c28]/90 border border-white/15 text-xs text-white font-bold"
          >
            {t.langBtn}
          </button>
        </div>

        <div className="w-full max-w-md space-y-6 my-auto pt-10 md:pt-0">
          
          {/* Main Glassmorphic Card */}
          <div className="bg-[#0f172a]/75 backdrop-blur-2xl border border-white/20 rounded-3xl p-6 sm:p-8 shadow-[0_30px_70px_rgba(0,0,0,0.8),0_0_40px_rgba(0,229,255,0.2)] space-y-6">
            
            {/* Header / Intro */}
            <div className="text-center space-y-2 pb-2 border-b border-white/10">
              <div className="inline-flex p-2.5 bg-[#0b0f17]/90 rounded-2xl border border-[#00e5ff]/30 shadow-xl shadow-cyan-950/50">
                <img src="/logo.png" alt="TeleTips Pro" className="h-9 w-auto object-contain filter drop-shadow-[0_0_12px_rgba(0,229,255,0.5)]" />
              </div>
              <h3 className="text-xl font-extrabold text-white">
                {mode === 'signup' ? t.cardSignUpTitle : t.cardSignInTitle}
              </h3>
              <p className="text-xs text-slate-300">
                {mode === 'signup' ? t.cardSignUpSub : t.cardSignInSub}
              </p>
            </div>

            {/* Error Message Toast */}
            {errorMessage && (
              <div className="p-3.5 bg-rose-500/15 border border-rose-500/30 rounded-xl text-rose-300 text-xs flex items-center gap-2">
                <svg className="w-4 h-4 flex-shrink-0 text-rose-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Fast Social Logins */}
            <div className="space-y-2.5">
              <span className="text-[11px] font-bold text-slate-400 block text-center uppercase tracking-wider">
                {t.socialHeader}
              </span>

              <div className="grid grid-cols-3 gap-2.5">
                
                {/* Google OAuth Button */}
                <button
                  type="button"
                  onClick={() => handleOAuth('oauth_google')}
                  disabled={Boolean(oauthLoading)}
                  className="flex items-center justify-center gap-1.5 py-3 px-3 rounded-xl bg-[#1c2536] hover:bg-[#263248] border border-white/15 hover:border-[#00e5ff]/50 text-white font-bold text-xs transition duration-200 shadow-md hover:shadow-[0_0_15px_rgba(0,229,255,0.25)] disabled:opacity-50 disabled:cursor-not-allowed group focus:outline-none focus:ring-2 focus:ring-[#00e5ff]/50"
                  title="Google"
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
                  <span>Google</span>
                </button>

                {/* Discord OAuth Button */}
                <button
                  type="button"
                  onClick={() => handleOAuth('oauth_discord')}
                  disabled={Boolean(oauthLoading)}
                  className="flex items-center justify-center gap-1.5 py-3 px-3 rounded-xl bg-[#1c2536] hover:bg-[#263248] border border-white/15 hover:border-[#5865F2]/60 text-white font-bold text-xs transition duration-200 shadow-md hover:shadow-[0_0_15px_rgba(88,101,242,0.35)] disabled:opacity-50 disabled:cursor-not-allowed group focus:outline-none focus:ring-2 focus:ring-[#5865F2]/50"
                  title="Discord"
                >
                  {oauthLoading === 'oauth_discord' ? (
                    <div className="w-4 h-4 rounded-full border-2 border-slate-600 border-t-[#5865F2] animate-spin" />
                  ) : (
                    <svg className="w-4 h-4 text-[#5865F2] flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.893.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
                    </svg>
                  )}
                  <span>Discord</span>
                </button>

                {/* Facebook OAuth Button */}
                <button
                  type="button"
                  onClick={() => handleOAuth('oauth_facebook')}
                  disabled={Boolean(oauthLoading)}
                  className="flex items-center justify-center gap-1.5 py-3 px-3 rounded-xl bg-[#1c2536] hover:bg-[#263248] border border-white/15 hover:border-[#1877F2]/60 text-white font-bold text-xs transition duration-200 shadow-md hover:shadow-[0_0_15px_rgba(24,119,242,0.35)] disabled:opacity-50 disabled:cursor-not-allowed group focus:outline-none focus:ring-2 focus:ring-[#1877F2]/50"
                  title="Facebook"
                >
                  {oauthLoading === 'oauth_facebook' ? (
                    <div className="w-4 h-4 rounded-full border-2 border-slate-600 border-t-[#1877F2] animate-spin" />
                  ) : (
                    <svg className="w-4 h-4 text-[#1877F2] flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
                    </svg>
                  )}
                  <span>Facebook</span>
                </button>
              </div>
            </div>

            {/* Visual Divider */}
            <div className="relative flex items-center justify-center">
              <div className="border-t border-white/10 w-full" />
              <span className="bg-[#151c28] px-3 text-[11px] text-slate-400 font-semibold uppercase whitespace-nowrap">
                {t.orEmail}
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
            <div className="text-center pt-2 text-xs text-slate-300">
              {mode === 'signup' ? (
                <p>
                  {t.haveAccount}{' '}
                  <Link to="/sign-in" className="text-[#00e5ff] font-bold hover:underline transition">
                    {t.signInLink}
                  </Link>
                </p>
              ) : (
                <p>
                  {t.noAccount}{' '}
                  <Link to="/sign-up" className="text-[#00e5ff] font-bold hover:underline transition">
                    {t.signUpLink}
                  </Link>
                </p>
              )}
            </div>
          </div>

          {/* Secure Trust Badge */}
          <div className="flex items-center justify-center gap-2 text-[11px] text-slate-400 font-medium drop-shadow-md">
            <svg className="w-3.5 h-3.5 text-[#10b981]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span>{t.clerkBadge}</span>
          </div>

        </div>
      </div>
    </div>
  );
};
