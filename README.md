# مهم قبل الرفع على Render

ملف التشغيل الرئيسي هو `server.py` وأمر التشغيل هو:

```bash
gunicorn server:app
```

ارفع **محتويات المجلد** إلى جذر مستودع GitHub. يجب أن يظهر `server.py` و`app.py` و`requirements.txt` مباشرة في الصفحة الرئيسية للمستودع. لا تستبدل `app.py` بملف `tests/test_app.py`.

---

# Paid Link Library — Flask + Moyasar

نسخة كاملة من مشروع مكتبة الروابط بعد إضافة:

- تسجيل حسابات وتسجيل دخول آمن.
- منع المكتبة عن أي مستخدم لا يملك اشتراكًا ساريًا.
- خطتان شهريتان/سنويتان قابلة لتعديل السعر والمدة من متغيرات البيئة.
- دفع عبر **Moyasar** والتحقق من العملية من الخادم قبل التفعيل.
- ربط الدفعة بالمستخدم والخطة وجلسة الدفع باستخدام Metadata.
- إضافة مدة التجديد إلى الاشتراك الحالي بدل استبدالها.
- لوحة مدير لإدارة المستخدمين والاشتراكات.
- إضافة/تعديل/حذف الروابط للمدير فقط، والمشتركون للبحث والفتح فقط.
- CSRF، كلمات مرور مشفرة، حماية من Open Redirect، وPOST للحذف والخروج.
- الحفاظ على جدول `link_item` الحالي وعدم حذف الروابط القديمة.

## 1) التشغيل محليًا

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

انسخ `.env.example` إلى `.env` أو عرّف القيم في النظام. Flask لا يقرأ `.env` تلقائيًا في Gunicorn، لذلك محليًا يمكنك تشغيل القيم من الطرفية أو تثبيت `python-dotenv` اختياريًا.

مثال Linux/macOS:

```bash
export SECRET_KEY="change-me"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="StrongPassword123!"
export MOYASAR_PUBLISHABLE_KEY="pk_test_..."
export MOYASAR_SECRET_KEY="sk_test_..."
python app.py
```

على Windows PowerShell:

```powershell
$env:SECRET_KEY="change-me"
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="StrongPassword123!"
$env:MOYASAR_PUBLISHABLE_KEY="pk_test_..."
$env:MOYASAR_SECRET_KEY="sk_test_..."
python app.py
```

ثم افتح: `http://127.0.0.1:5000`

## 2) إعداد حساب المدير

ضع المتغيرات التالية **قبل أول تشغيل**:

```text
ADMIN_NAME=Site Admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=StrongPassword123!
```

سيُنشأ المدير تلقائيًا. إذا كان البريد موجودًا فسيتم ترقيته إلى مدير. لا تتغير كلمة المرور بعد ذلك إلا إذا وضعت مؤقتًا:

```text
RESET_ADMIN_PASSWORD=1
```

ثم أعدها إلى `0` بعد التشغيل.

## 3) إعداد Moyasar

1. أنشئ حساب Moyasar واستخدم وضع الاختبار أولًا.
2. انسخ `Publishable Key` و`Secret Key`.
3. أضف:

```text
MOYASAR_PUBLISHABLE_KEY=pk_test_...
MOYASAR_SECRET_KEY=sk_test_...
APP_BASE_URL=https://your-domain.com
COOKIE_SECURE=1
```

المفتاح السري لا يظهر في HTML. الخادم يجلب العملية من Moyasar ويتحقق من:

- `status = paid`
- المبلغ
- العملة `SAR`
- `user_id`
- الخطة
- رمز جلسة الدفع
- عدم استخدام رقم العملية سابقًا

> الأسعار في المتغيرات بالهللات: `4900` = `49.00 SAR`.

## 4) قاعدة البيانات

محليًا يعمل SQLite تلقائيًا. للإنتاج استخدم PostgreSQL (Supabase أو Render) وضع رابط الاتصال في:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/postgres
```

الكود يحول الرابط تلقائيًا إلى `postgresql+psycopg://`.

إذا كانت لديك قاعدة المشروع القديمة، استخدم **نفس DATABASE_URL**؛ جدول الروابط الحالي `link_item` سيبقى كما هو، وستُضاف جداول المستخدمين والمدفوعات والاشتراكات.

## 5) النشر على Render

يمكن استخدام `render.yaml` أو إنشاء Web Service يدويًا:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn server:app
Health Check: /health
```

أضف جميع المتغيرات المهمة في Environment، خصوصًا:

```text
SECRET_KEY
DATABASE_URL
APP_BASE_URL
COOKIE_SECURE=1
ADMIN_EMAIL
ADMIN_PASSWORD
MOYASAR_PUBLISHABLE_KEY
MOYASAR_SECRET_KEY
```

## 6) تعديل الأسعار

```text
MONTHLY_PRICE_HALALAS=4900
MONTHLY_SUBSCRIPTION_DAYS=30
YEARLY_PRICE_HALALAS=49000
YEARLY_SUBSCRIPTION_DAYS=365
```

## 7) قبل استقبال مدفوعات حقيقية

- استخدم نطاقًا وHTTPS.
- استبدل مفاتيح الاختبار بمفاتيح Live.
- اختبر الدفع الناجح والفاشل وانتهاء الاشتراك.
- عدّل صفحات الشروط والخصوصية وسياسة الاسترجاع ببيانات منشأتك.
- تأكد من المتطلبات النظامية والضريبية لنشاطك.
- لا ترفع `.env` أو المفاتيح السرية إلى GitHub.

## ملاحظة عن الاشتراك

التنفيذ الحالي عبارة عن اشتراك مدفوع لمدة محددة يُجدد بالدفع. لا يخصم تلقائيًا كل شهر من البطاقة. الخصم التلقائي يحتاج تفعيل Tokenization/Recurring Payments من Moyasar واتفاقية واضحة مع العميل وجدولة آمنة للخصم.
