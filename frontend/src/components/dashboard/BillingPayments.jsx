import React, { useState } from 'react';

export const BillingPayments = ({
  currentLang = 'ar'
}) => {
  const isRTL = currentLang === 'ar';
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [cryptoCoin, setCryptoCoin] = useState('usdttrc20');
  const [copied, setCopied] = useState(false);

  const plans = [
    {
      id: 'weekly',
      nameAr: 'باقة أسبوع (Starter)',
      nameEn: 'Starter Plan (7 Days)',
      price: '$5',
      durationAr: '/ 7 أيام',
      durationEn: '/ 7 Days',
      popular: false,
      featuresAr: ['توجيه فوري لحظي (< 1s)', 'قنوات غير محدودة', 'تعديل النصوص واستبدال الروابط'],
      featuresEn: ['Instant forwarding (< 1s)', 'Unlimited target channels', 'Content transforms & link replacement']
    },
    {
      id: 'monthly',
      nameAr: 'باقة شهر (Pro)',
      nameEn: 'Pro Plan (30 Days)',
      price: '$15',
      durationAr: '/ 30 يوم',
      durationEn: '/ 30 Days',
      popular: true,
      featuresAr: ['كافة ميزات الباقة الأساسية', 'تجميع ألبومات الصور كاملة', 'تخطي قيود القنوات المحمية', 'فلترة الكلمات المفتاحية الذكية'],
      featuresEn: ['All Starter features', 'Full album & multi-media support', 'Auto-bypass restricted channels', 'Smart keyword & regex filtering']
    },
    {
      id: 'annual',
      nameAr: 'باقة سنة كاملة (Enterprise VIP)',
      nameEn: 'Enterprise VIP (365 Days)',
      price: '$110',
      durationAr: '/ 365 يوم',
      durationEn: '/ 365 Days',
      popular: false,
      featuresAr: ['وصول كامل VIP لكافة الميزات', 'أعلى أولوية في المعالجة والسرعة', 'دعم فني استثنائي 24/7 وتحديثات مبكرة'],
      featuresEn: ['Full unlimited VIP access', 'Highest dedicated server priority', '24/7 dedicated 1-on-1 priority support']
    }
  ];

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      
      {/* Header */}
      <div className="text-center space-y-2 py-4">
        <h2 className="text-2xl sm:text-3xl font-black text-white">
          {isRTL ? 'باقات الاشتراك والتفعيل الفوري بالعملات الرقمية' : 'Automated Crypto Subscriptions & Pricing'}
        </h2>
        <p className="text-xs sm:text-sm text-slate-400 max-w-xl mx-auto">
          {isRTL 
            ? 'يتم تفعيل اشتراكك لحظياً عبر محرك الـ NOWPayments Webhook الآمن فور تأكيد المعاملة على البلوكتشين.'
            : 'Instant automated account activation powered by NOWPayments blockchain Webhooks.'
          }
        </p>
      </div>

      {/* Pricing Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {plans.map((p) => (
          <div
            key={p.id}
            className={`glass-card rounded-2xl p-6 flex flex-col justify-between relative group ${
              p.popular ? 'border-2 border-accent-cyan/60 shadow-glow-cyan' : ''
            }`}
          >
            {p.popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-accent-cyan to-accent-indigo text-slate-950 font-black text-[10px] uppercase px-3 py-0.5 rounded-full shadow-md tracking-wider">
                POPULAR • BEST VALUE
              </div>
            )}

            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-bold text-white">
                  {isRTL ? p.nameAr : p.nameEn}
                </h3>
                <div className="flex items-baseline space-x-1 rtl:space-x-reverse mt-2">
                  <span className="text-3xl font-black text-white font-mono">{p.price}</span>
                  <span className="text-xs text-slate-400">{isRTL ? p.durationAr : p.durationEn}</span>
                </div>
              </div>

              <ul className="space-y-2.5 text-xs text-slate-300 border-t border-glass-border pt-4">
                {(isRTL ? p.featuresAr : p.featuresEn).map((feat, i) => (
                  <li key={i} className="flex items-center space-x-2 rtl:space-x-reverse">
                    <span className="text-accent-emerald font-bold">✓</span>
                    <span>{feat}</span>
                  </li>
                ))}
              </ul>
            </div>

            <button
              onClick={() => setSelectedPlan(p)}
              className={`mt-6 w-full py-3 rounded-xl font-bold text-xs transition active:scale-95 ${
                p.popular
                  ? 'bg-gradient-to-r from-accent-cyan to-accent-indigo text-slate-950 font-black shadow-glow-cyan'
                  : 'bg-surface-800 hover:bg-surface-700 text-white'
              }`}
            >
              {isRTL ? 'شراء وتفعيل لحظي ➔' : 'Checkout & Activate ➔'}
            </button>
          </div>
        ))}
      </div>

      {/* NOWPayments Checkout Modal */}
      {selectedPlan && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="glass-card rounded-2xl max-w-md w-full p-6 space-y-5 bg-surface-900 border border-glass-border animate-fade-in">
            <div className="flex items-center justify-between border-b border-glass-border pb-3">
              <div>
                <h3 className="font-bold text-white text-base">
                  {isRTL ? 'بوابة الدفع والتفعيل الفوري' : 'Crypto Checkout Gateway'}
                </h3>
                <p className="text-xs text-slate-400">{isRTL ? selectedPlan.nameAr : selectedPlan.nameEn} ({selectedPlan.price})</p>
              </div>
              <button 
                onClick={() => setSelectedPlan(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg bg-surface-800"
              >
                ✕
              </button>
            </div>

            {/* Crypto Coin Selector */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-300">
                {isRTL ? 'اختر العملة والشبكة المفضلة:' : 'Select Currency & Network:'}
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: 'usdttrc20', name: 'USDT (TRC20)' },
                  { id: 'btc', name: 'Bitcoin (BTC)' },
                  { id: 'eth', name: 'Ethereum (ETH)' },
                ].map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setCryptoCoin(c.id)}
                    className={`py-2 px-2 rounded-xl text-xs font-mono font-bold transition border ${
                      cryptoCoin === c.id
                        ? 'bg-accent-cyan/15 text-accent-cyan border-accent-cyan/50 shadow-glow-cyan'
                        : 'bg-surface-950 text-slate-400 border-slate-800 hover:text-white'
                    }`}
                  >
                    {c.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Address & QR Placeholder */}
            <div className="p-4 rounded-xl bg-surface-950 border border-slate-800 text-center space-y-3">
              <div className="w-28 h-28 mx-auto bg-white rounded-xl flex items-center justify-center p-2 shadow-md">
                {/* Visual QR Code simulation */}
                <div className="w-full h-full border-2 border-slate-900 border-dashed rounded flex items-center justify-center font-mono text-[10px] text-slate-900 font-bold">
                  [LIVE QR CODE]
                </div>
              </div>

              <div>
                <span className="text-[10px] text-slate-500 block uppercase font-mono tracking-wider">Deposit Address ({cryptoCoin.toUpperCase()}):</span>
                <div className="flex items-center justify-center space-x-1 rtl:space-x-reverse mt-1">
                  <span className="font-mono text-xs text-cyan-300 select-all truncate max-w-[260px]">
                    TYDzsXDvGzX5V9Jp4R2KqM8N7LsV...
                  </span>
                  <button
                    onClick={() => handleCopy('TYDzsXDvGzX5V9Jp4R2KqM8N7LsV893K')}
                    className="px-2 py-1 bg-surface-800 hover:bg-surface-700 text-white rounded text-[11px] font-bold"
                  >
                    {copied ? '✓ Copied' : 'Copy'}
                  </button>
                </div>
              </div>
            </div>

            {/* Blockchain IPN Monitor */}
            <div className="flex items-center justify-between text-xs font-mono text-slate-400 pt-2 border-t border-glass-border">
              <span className="flex items-center space-x-1.5 rtl:space-x-reverse">
                <span className="w-2 h-2 rounded-full bg-accent-cyan animate-radar-ping" />
                <span>Monitoring Blockchain...</span>
              </span>
              <span className="text-accent-emerald font-bold">Live IPN</span>
            </div>

          </div>
        </div>
      )}

    </div>
  );
};

export default BillingPayments;
