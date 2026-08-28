import React, { useState } from 'react';
import {
  BookOpen,
  Zap,
  CheckCircle2,
  AlertCircle,
  Target,
  Sparkles,
  Copy,
  Check,
  FileText,
  Scissors,
  PlusCircle,
  Heading,
  Code2,
  HelpCircle,
  Layers,
  ShieldCheck,
  Send,
  Hash,
  Terminal,
  Info,
  Radio,
  ArrowLeft,
  ChevronLeft
} from 'lucide-react';

const DocumentationTab = () => {
  const [copiedCode, setCopiedCode] = useState(null);

  const handleCopy = (code, id) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(id);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const cheatSheetItems = [
    {
      id: 'usernames',
      title: 'حذف جميع المعرفات واليوزرات (@username)',
      pattern: '@[a-zA-Z0-9_]+',
      type: 'Regex',
      replacement: '(فارغ للحذف)',
      description: 'يقوم بمسح أي اسم مستخدم أو منشن يبدأ بـ @ في نص الرسالة.',
      example: 'تابعونا @channel_name -> تابعونا'
    },
    {
      id: 'links',
      title: 'حذف جميع روابط المواقع والتليجرام',
      pattern: 'https?:\\/\\/\\S+|t\\.me\\/\\S+',
      type: 'Regex',
      replacement: '(فارغ للحذف)',
      description: 'يحذف أي رابط يبدأ بـ http أو https أو روابط تليجرام t.me.',
      example: 'رابط الخبر https://t.me/news -> رابط الخبر'
    },
    {
      id: 'hashtags',
      title: 'حذف جميع الهاشتاجات (#هاشتاج)',
      pattern: '#[a-zA-Z0-9_\\u0600-\\u06FF]+',
      type: 'Regex',
      replacement: '(فارغ للحذف)',
      description: 'يزيل الهاشتاجات العربية والإنجليزية من المنشور.',
      example: '#أخبار_اليوم #crypto -> (تم الحذف)'
    },
    {
      id: 'footer_brand',
      title: 'إضافة تذييل وحقوق القناة الرسمية',
      pattern: '(اتركه فارغاً)',
      type: 'Footer',
      replacement: 'قناتنا الرسمية: https://t.me/your_channel',
      description: 'يضيف رابط وحقوق قناتك في نهاية المنشور بعد ترك سطرين فاصلين.',
      example: 'نص الخبر ... \n\nقناتنا الرسمية: https://t.me/your_channel'
    },
    {
      id: 'prefix_urgent',
      title: 'إضافة ترويسة وعنوان في بداية الخبر',
      pattern: '(اتركه فارغاً)',
      type: 'Prefix',
      replacement: 'عاجل | ',
      description: 'يضيف كلمة أو ترويسة في أول سطر قبل نص المنشور.',
      example: 'عاجل | أعلنت الشركة اليوم عن...'
    },
    {
      id: 'word_replace',
      title: 'استبدال اسم المصدر باسم قناتك',
      pattern: 'قناة الجزيرة',
      type: 'Replace',
      replacement: 'شبكة الأخبار الخاصة',
      description: 'استبدال مباشر ودقيق لأي كلمة محددة.',
      example: 'المصدر: قناة الجزيرة -> المصدر: شبكة الأخبار الخاصة'
    }
  ];

  return (
    <div dir="rtl" className="space-y-6 text-slate-200 animate-fadeIn">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-surface-900 via-surface-850 to-surface-900 border border-slate-700/80 p-6 sm:p-8 shadow-xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="inline-flex items-center space-x-2 space-x-reverse px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold">
              <BookOpen className="w-3.5 h-3.5" />
              <span>دليل الاستخدام والتوثيق البرمجي</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              دليل تشغيل وإدارة Telegram Forwarder Pro
            </h1>
            <p className="text-sm text-slate-400 max-w-2xl leading-relaxed">
              مرجع شامل يوضح كيفية ضبط مسارات التوجيه اللحظي، تخصيص القواعد لكل قناة، واستخدام التعبيرات النمطية (Regex) لمعالجة النصوص بدقة.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="px-4 py-2.5 rounded-xl bg-slate-800/80 border border-slate-700 text-xs font-mono text-emerald-400 flex items-center gap-2">
              <Radio className="w-4 h-4 text-emerald-400 animate-pulse" />
              <span>البث اللحظي: &lt; 1 ثانية</span>
            </div>
          </div>
        </div>
      </div>

      {/* 1. Quick Start Guide Section */}
      <div className="rounded-2xl bg-surface-900 border border-slate-800 p-6 space-y-6 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3 space-x-reverse">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">البداية السريعة (Quick Start Guide)</h2>
              <p className="text-xs text-slate-400">خطوات متسلسلة لربط القنوات وضمان سرعة التوجيه اللحظي</p>
            </div>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded-lg bg-slate-800 text-slate-400">3 خطوات</span>
        </div>

        {/* 3 Step Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Step 1 */}
          <div className="relative p-5 rounded-xl bg-surface-850 border border-slate-800 hover:border-slate-700 transition space-y-3">
            <div className="flex items-center justify-between">
              <span className="w-7 h-7 rounded-lg bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 flex items-center justify-center text-xs font-bold font-mono">01</span>
              <Target className="w-4 h-4 text-slate-500" />
            </div>
            <h3 className="text-sm font-bold text-white">تحديد القناة المصدر</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              تأكد من انضمام حساب التوجيه (<code className="text-indigo-300 font-mono">@ayg1133</code>) إلى القناة المصدر، ثم انسخ معرف الـ ID الرقمي (مثل <code className="text-slate-300 font-mono">-1001234567890</code>).
            </p>
          </div>

          {/* Step 2 */}
          <div className="relative p-5 rounded-xl bg-surface-850 border border-slate-800 hover:border-slate-700 transition space-y-3">
            <div className="flex items-center justify-between">
              <span className="w-7 h-7 rounded-lg bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-xs font-bold font-mono">02</span>
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            </div>
            <h3 className="text-sm font-bold text-white">ترقية الحساب لمشرف في الهدف</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              أضف حساب التوجيه كمشرف (Admin) في كافة القنوات الهدف، مع تفعيل صلاحية <strong className="text-emerald-300 font-medium">"نشر الرسائل (Post Messages)"</strong>.
            </p>
          </div>

          {/* Step 3 */}
          <div className="relative p-5 rounded-xl bg-surface-850 border border-slate-800 hover:border-slate-700 transition space-y-3">
            <div className="flex items-center justify-between">
              <span className="w-7 h-7 rounded-lg bg-cyan-600/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center text-xs font-bold font-mono">03</span>
              <Send className="w-4 h-4 text-cyan-400" />
            </div>
            <h3 className="text-sm font-bold text-white">إنشاء مسار التوجيه</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              اضغط على "إضافة مسار جديد"، حدد المصدر والأهداف المرجوة واختر أنواع الوسائط المراد نقلها ثم اضغط حفظ.
            </p>
          </div>
        </div>

        {/* Admin Permission Alert Banner */}
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start space-x-3 space-x-reverse">
          <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs text-slate-300 leading-relaxed">
            <span className="font-bold text-amber-300 block">تنبيه هام حول روابط الدعوة المؤقتة (Invite Links):</span>
            <p>
              يُفضل دائماً استخدام <strong>معرف القناة ID الرقمي</strong> (مثل <code className="text-amber-200 font-mono bg-slate-900 px-1 py-0.5 rounded">-1001234567890</code>) أو اسم المستخدم (<code className="text-amber-200 font-mono bg-slate-900 px-1 py-0.5 rounded">@channel</code>) بدلاً من روابط الدعوة الخاصة (<code className="text-amber-400 font-mono">t.me/+...</code>)، لتفادي قيود فترات الانتظار (FloodWait) التي يفرضها تليجرام على فحص الروابط.
            </p>
          </div>
        </div>
      </div>

      {/* 2. Scope Control Section */}
      <div className="rounded-2xl bg-surface-900 border border-slate-800 p-6 space-y-6 shadow-sm">
        <div className="flex items-center space-x-3 space-x-reverse border-b border-slate-800 pb-4">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center">
            <Target className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">نطاق تطبيق القواعد (Scope Control)</h2>
            <p className="text-xs text-slate-400">التحكم في تخصيص التعديلات لكل قناة بشكل مستقل أو عام</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Global Rules */}
          <div className="p-5 rounded-xl bg-surface-850 border border-slate-800 space-y-3">
            <div className="inline-flex items-center space-x-1.5 space-x-reverse px-2.5 py-1 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-300 text-xs font-semibold">
              <Layers className="w-3.5 h-3.5" />
              <span>القواعد العامة (Global Rules)</span>
            </div>
            <h3 className="text-sm font-bold text-white">تطبيق التعديل على جميع القنوات</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              عند ترك خانة <strong className="text-slate-200">"نطاق تطبيق القاعدة (القناة الهدف)"</strong> فارغة، سيقوم المحرك بتنفيذ قاعدة التعديل (مثل حذف الروابط أو استبدال اسم) على <strong>جميع الرسائل المنقولة لأي قناة هدف</strong> تلقائياً.
            </p>
            <div className="p-3 bg-slate-900/90 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-400">
              Target Channel Scope: <span className="text-emerald-400 font-bold">null (All Targets)</span>
            </div>
          </div>

          {/* Target Specific Rules */}
          <div className="p-5 rounded-xl bg-surface-850 border border-slate-800 space-y-3">
            <div className="inline-flex items-center space-x-1.5 space-x-reverse px-2.5 py-1 rounded-md bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 text-xs font-semibold">
              <Target className="w-3.5 h-3.5" />
              <span>قواعد مخصصة (Channel-Specific)</span>
            </div>
            <h3 className="text-sm font-bold text-white">تخصيص تذييل أو استبدال لقناة معينة</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              عند وضع معرّف قناة محددة في خانة النطاق، سيتم تفعيل التعديل <strong>فقط وحصرياً عند الإرسال لتلك القناة</strong>. يمكنك مثلاً وضع تذييل خاص بالقناة A، وتذييل مختلف تماماً لقناة VIP B من نفس القناة المصدر.
            </p>
            <div className="p-3 bg-slate-900/90 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-400">
              Target Channel Scope: <span className="text-cyan-400 font-bold">-1002233445566</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Transformations Guide Section */}
      <div className="rounded-2xl bg-surface-900 border border-slate-800 p-6 space-y-6 shadow-sm">
        <div className="flex items-center space-x-3 space-x-reverse border-b border-slate-800 pb-4">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">أنواع تحويل النصوص (Transformations Guide)</h2>
            <p className="text-xs text-slate-400">شرح تفصيلي للخيارات الـ 5 المتاحة في القائمة المنسدلة لمعالجة المحتوى</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* 1. Replace */}
          <div className="p-4 rounded-xl bg-surface-850 border border-slate-800 hover:border-slate-700 transition space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-0.5 text-xs font-bold rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">Replace</span>
              <FileText className="w-4 h-4 text-slate-500" />
            </div>
            <h4 className="text-sm font-bold text-white">استبدال نص مباشر (Direct Text Replace)</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              استبدال كلمة أو رابط محدد بنص بديل بدقة تامة.
            </p>
            <div className="text-[11px] font-mono bg-slate-900 p-2 rounded border border-slate-800 text-slate-300">
              <span className="text-rose-400">@old_channel</span> ➔ <span className="text-emerald-400">@new_channel</span>
            </div>
          </div>

          {/* 2. Regex */}
          <div className="p-4 rounded-xl bg-surface-850 border border-slate-800 hover:border-slate-700 transition space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-0.5 text-xs font-bold rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">Regex</span>
              <Code2 className="w-4 h-4 text-slate-500" />
            </div>
            <h4 className="text-sm font-bold text-white">تعبير نمطي متقدم (Regular Expression)</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              معالجة الأنماط المتغيرة مثل حذف جميع الروابط أو أي معرف يبدأ بـ @.
            </p>
            <div className="text-[11px] font-mono bg-slate-900 p-2 rounded border border-slate-800 text-slate-300">
              Pattern: <span className="text-cyan-400">@[a-zA-Z0-9_]+</span>
            </div>
          </div>

          {/* 3. Strip */}
          <div className="p-4 rounded-xl bg-surface-850 border border-slate-800 hover:border-slate-700 transition space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-0.5 text-xs font-bold rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">Strip</span>
              <Scissors className="w-4 h-4 text-slate-500" />
            </div>
            <h4 className="text-sm font-bold text-white">حذف وإزالة (Strip Pattern / Remove)</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              مسح وحذف عبارات الإعلانات والروابط المزعجة من الرسالة دون ترك أثر.
            </p>
            <div className="text-[11px] font-mono bg-slate-900 p-2 rounded border border-slate-800 text-slate-300">
              Target: <span className="text-rose-400">"اشترك في القناة"</span> ➔ <span className="text-slate-500">(حذف)</span>
            </div>
          </div>

          {/* 4. Footer */}
          <div className="p-4 rounded-xl bg-surface-850 border border-slate-800 hover:border-slate-700 transition space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-0.5 text-xs font-bold rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Footer</span>
              <PlusCircle className="w-4 h-4 text-slate-500" />
            </div>
            <h4 className="text-sm font-bold text-white">إضافة تذييل (Append Custom Footer)</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              إضافة توقيع وقنوات التواصل في نهاية كل منشور مع سطرين فارغين تلقائياً.
            </p>
            <div className="text-[11px] font-mono bg-slate-900 p-2 rounded border border-slate-800 text-emerald-400">
              \n\n📢 تابعنا: @my_channel
            </div>
          </div>

          {/* 5. Prefix */}
          <div className="p-4 rounded-xl bg-surface-850 border border-slate-800 hover:border-slate-700 transition space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="px-2.5 py-0.5 text-xs font-bold rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">Prefix</span>
              <Heading className="w-4 h-4 text-slate-500" />
            </div>
            <h4 className="text-sm font-bold text-white">إضافة ترويسة (Prepend Custom Prefix)</h4>
            <p className="text-xs text-slate-400 leading-relaxed">
              وضع كلمة ترويجية أو عنوان رئيسي في السطر الأول أعلى المنشور.
            </p>
            <div className="text-[11px] font-mono bg-slate-900 p-2 rounded border border-slate-800 text-amber-300">
              ⚡ عاجل | \n(نص الخبر)
            </div>
          </div>
        </div>
      </div>

      {/* 4. Regex & Common Rules Cheat Sheet Section */}
      <div className="rounded-2xl bg-surface-900 border border-slate-800 p-6 space-y-6 shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3 space-x-reverse">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">جدول الأكواد الجاهزة (Regex & Common Cheat Sheet)</h2>
              <p className="text-xs text-slate-400">أكثر الأكواد استخداماً لحذف الروابط وتعديل المنشورات مع إمكانية النسخ الفوري</p>
            </div>
          </div>
        </div>

        {/* Cheat Sheet Table */}
        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-surface-850">
          <table className="w-full text-right text-xs">
            <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-800 font-semibold">
              <tr>
                <th className="py-3 px-4">الوظيفة والهدف</th>
                <th className="py-3 px-4">النوع (Type)</th>
                <th className="py-3 px-4">كود النمط (Pattern)</th>
                <th className="py-3 px-4">القيمة البديلة (Replacement)</th>
                <th className="py-3 px-4 text-center">نسخ الكود</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-300">
              {cheatSheetItems.map((item) => (
                <tr key={item.id} className="hover:bg-slate-800/40 transition">
                  <td className="py-3.5 px-4">
                    <p className="font-bold text-white">{item.title}</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">{item.description}</p>
                  </td>
                  <td className="py-3.5 px-4">
                    <span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded ${
                      item.type === 'Regex' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' :
                      item.type === 'Footer' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                      item.type === 'Prefix' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                      'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
                    }`}>
                      {item.type}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 font-mono font-bold text-cyan-300 text-[11px]">
                    {item.pattern}
                  </td>
                  <td className="py-3.5 px-4 font-mono text-slate-400 text-[11px] max-w-xs truncate">
                    {item.replacement}
                  </td>
                  <td className="py-3.5 px-4 text-center">
                    <button
                      onClick={() => handleCopy(item.pattern !== '(اتركه فارغاً)' ? item.pattern : item.replacement, item.id)}
                      className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition inline-flex items-center gap-1 text-xs"
                      title="نسخ الكود"
                    >
                      {copiedCode === item.id ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                          <span className="text-emerald-400 font-semibold">تم النسخ</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          <span>نسخ</span>
                        </>
                      )}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. Troubleshooting & Priorities Section */}
      <div className="rounded-2xl bg-surface-900 border border-slate-800 p-6 space-y-6 shadow-sm">
        <div className="flex items-center space-x-3 space-x-reverse border-b border-slate-800 pb-4">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center">
            <HelpCircle className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">الأسئلة الشائعة وتصحيح الأخطاء (Troubleshooting)</h2>
            <p className="text-xs text-slate-400">إرشادات حل المشاكل وفهم نظام أولوية القواعد (Priority Precedence)</p>
          </div>
        </div>

        <div className="space-y-4">
          {/* FAQ 1 */}
          <div className="p-4 rounded-xl bg-surface-850 border border-slate-800 space-y-2">
            <div className="flex items-center space-x-2 space-x-reverse font-bold text-sm text-white">
              <Info className="w-4 h-4 text-indigo-400" />
              <h4>كيف يعمل نظام الأولوية (Priority) عند وجود أكثر من قاعدة؟</h4>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed pr-6">
              يتم تنفيذ القواعد بترتيب تصاعدي حسب رقم الأولوية (<strong className="text-slate-200">الرقم 1 ينفذ أولاً</strong>، ثم الرقم 2، ثم الرقم 3). احرص على وضع قواعد الحذف أو الاستبدال العام بالأولوية 1، وقواعد إضافة التذييل (Footer) بأولوية أعلى (مثل 10) حتى لا يتم مسح التذييل بقواعد الحذف السابقة.
            </p>
          </div>

          {/* FAQ 2 */}
          <div className="p-4 rounded-xl bg-surface-850 border border-slate-800 space-y-2">
            <div className="flex items-center space-x-2 space-x-reverse font-bold text-sm text-white">
              <Info className="w-4 h-4 text-indigo-400" />
              <h4>لماذا تظهر رسالة خطأ "Account has no permission to send messages"؟</h4>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed pr-6">
              هذا يعني أن حساب التوجيه (<code className="text-indigo-300 font-mono">@ayg1133</code>) ليس مشرفاً في القناة الهدف أو أن صلاحية "نشر الرسائل" معطلة عنه في إعدادات القناة. قم بالدخول إلى إدارة القناة وتفعيل كامل الصلاحيات للمشرف.
            </p>
          </div>

          {/* FAQ 3 */}
          <div className="p-4 rounded-xl bg-surface-850 border border-slate-800 space-y-2">
            <div className="flex items-center space-x-2 space-x-reverse font-bold text-sm text-white">
              <Info className="w-4 h-4 text-indigo-400" />
              <h4>ما هو الحد الأقصى لأحرف الرسالة عند توجيه الصور أو الفيديوهات؟</h4>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed pr-6">
              يفرض تليجرام حداً أقصى قدره <strong className="text-amber-300">1024 حرفاً</strong> للنصوص المرفقة مع الصور والفيديوهات (Caption). إذا كان التذييل طويلاً جداً وتجاوز الحد، سيسجل المحرك خطأ <code className="text-rose-400 font-mono">MediaCaptionTooLongError</code> ولن يرسل المنشور. احرص على إبقاء التذييل موجزاً.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocumentationTab;
