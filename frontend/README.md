# TeleTips Pro — React + Clerk Authentication Integration

دليل ربط وتشغيل واجهة المستخدم مع خدمة **Clerk** لإدارة الحسابات وتسجيل الدخول.

## 🚀 التثبيت والتشغيل (Quick Start)

### 1. تثبيت الحزم:
```bash
npm install
# أو
pnpm install
```

### 2. إعداد مفاتيح Clerk في ملف `.env`:
```env
VITE_CLERK_PUBLISHABLE_KEY=pk_test_your_clerk_publishable_key_here
VITE_API_URL=http://localhost:5000
```

### 3. تشغيل خادم التطوير:
```bash
npm run dev
```

---

## 🎨 التخصيص والثيم (Custom Appearance Theme)
تم تصميم كائن التخصيص `teletipsClerkAppearance` في `src/theme/clerkTheme.js` ليوفر:
- **Dark Glassmorphic Card**: خلفية داكنة بلورية (`#0F172A`) مع تدرج ظلال سيان خفيفة.
- **Neon Cyan Glow Buttons**: أزرار تفاعلية بلون متدرج (`#4f46e5` إلى `#06b6d4`).
- **Typography**: خطوط عصرية أنيقة باللون الأبيض والرصاصي.

---

## 🛡️ حماية المسارات (Route Protection)
يستخدم المكون `<ProtectedRoute>` لمنع الوصول غير المصرح به للوحة التحكم، حيث يتم توجيه الزائر غير المسجل تلقائياً إلى صفحة `/sign-in`.
