# Quality Reference Library — English, 7-Day Trial, and Saudi Mada Payments

A complete Flask website with an English interface, a one-time free trial, protected engineering content, and Saudi Mada card payments through Moyasar.

## Main features

- Every newly registered user receives a one-time free trial, set to 7 days by default.
- Full library access is available during the trial without payment-card details.
- After the trial expires, protected library pages and links redirect the user to the subscription page.
- Monthly and annual paid plans using Saudi Mada cards through Moyasar.
- Paying before the trial ends does not remove unused trial time; the paid period is added after the trial expiration.
- Renewing an active subscription adds the new period after the current paid expiration.
- Fully English interface, messages, checkout, account pages, administration, terms, and privacy templates.
- Secure registration and sign-in with hashed passwords.
- Server-side verification of payment status, amount, currency, user metadata, plan, checkout token, payment uniqueness, source type, and Mada network.
- Administrator account with permanent access.
- Administrator controls for paid-day activation, paid-access revocation, and account disabling.
- Administrator-only link creation, editing, and deletion.
- CSRF protection, secure cookies, safe redirects, SQLite support, and PostgreSQL support.
- Safe database upgrade that preserves existing users, links, and payments.

## Trial behavior

The default duration is controlled by:

```text
FREE_TRIAL_DAYS=7
```

For a new account:

1. The trial starts immediately after successful registration.
2. The user is sent directly to `/library`.
3. The user can search and open protected links until `trial_end`.
4. After expiration, `/library` and protected link routes redirect to `/subscribe`.
5. The same account never receives another automatic trial.

When this version is deployed over the previous database, the application automatically adds `trial_start` and `trial_end` columns. Existing non-admin accounts that have no trial record and no currently active paid subscription receive one trial starting at the first deployment of this version. Existing active paid subscribers are marked as having already passed the trial so they will not receive a second trial later.

## Important deployment structure

Upload the **contents of this folder** to the root of the GitHub repository. The repository home page must show these entries directly:

```text
server.py
app.py
requirements.txt
Procfile
render.yaml
templates/
static/
tests/
```

The correct Render start command is:

```bash
gunicorn server:app
```

## 1. Local installation

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux or macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` values into your environment, then run:

```bash
python server.py
```

Open:

```text
http://127.0.0.1:5000
```

## 2. Administrator account

```text
ADMIN_NAME=Site Administrator
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=StrongPassword123!
RESET_ADMIN_PASSWORD=0
```

The administrator account is created automatically and does not require a trial or subscription.

To reset its password, temporarily set:

```text
RESET_ADMIN_PASSWORD=1
```

Redeploy, sign in, then restore it to:

```text
RESET_ADMIN_PASSWORD=0
```

## 3. Moyasar and Mada setup

Begin with Moyasar test keys:

```text
MOYASAR_PUBLISHABLE_KEY=pk_test_...
MOYASAR_SECRET_KEY=sk_test_...
APP_BASE_URL=https://your-domain.onrender.com
COOKIE_SECURE=1
```

The payment form is limited to Mada:

```javascript
methods: ['creditcard'],
supported_networks: ['mada'],
language: 'en'
```

The server activates paid access only after checking:

```text
status = paid
amount = selected plan price
currency = SAR
metadata user_id = signed-in user
metadata plan_code = selected plan
metadata checkout_token = pending checkout token
source.type = creditcard
source.company = mada
payment ID has not been used previously
```

Live Mada processing must be enabled in your Moyasar merchant account.

## 4. Database

Local SQLite:

```text
DATABASE_URL=sqlite:///local_links.db
```

Production PostgreSQL, including Supabase or Render:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/postgres
```

Keep the same production `DATABASE_URL` to preserve the existing library and accounts. The application upgrades the existing `app_user` table automatically without deleting data.

## 5. Render deployment

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn server:app
Health Check Path: /health
```

Required environment variables:

```text
SECRET_KEY
DATABASE_URL
APP_BASE_URL
COOKIE_SECURE=1
FREE_TRIAL_DAYS=7
ADMIN_NAME
ADMIN_EMAIL
ADMIN_PASSWORD
RESET_ADMIN_PASSWORD=0
MOYASAR_PUBLISHABLE_KEY
MOYASAR_SECRET_KEY
```

After replacing the GitHub files:

```text
Manual Deploy → Clear build cache & deploy
```

## 6. Prices and durations

Prices are in halalas:

```text
MONTHLY_PRICE_HALALAS=4900
MONTHLY_SUBSCRIPTION_DAYS=30
YEARLY_PRICE_HALALAS=49000
YEARLY_SUBSCRIPTION_DAYS=365
FREE_TRIAL_DAYS=7
```

Examples:

```text
4900 = SAR 49.00
49000 = SAR 490.00
```

## 7. Testing

```bash
python -m unittest discover -s tests -v
```

The tests cover:

- Automatic 7-day trial creation.
- Library access during the trial.
- Blocking access after the trial expires.
- Preventing an expired trial from being reset.
- Administrator link management.
- Verified Mada payment activation after the remaining trial time.
- Rejection of a paid transaction from a non-Mada network.

## 8. Before live launch

- Complete Moyasar merchant onboarding and enable Mada.
- Replace test API keys with live keys.
- Use HTTPS and set `COOKIE_SECURE=1`.
- Set `APP_BASE_URL` to the exact public HTTPS domain without a trailing slash.
- Test registration, trial expiration, successful payment, declined payment, and 3-D Secure flows.
- Replace the starter legal pages with reviewed Terms, Privacy, Refund, and Cancellation policies.
- Never commit `.env`, database passwords, secret keys, or live credentials to GitHub.

## Billing behavior

This project sells fixed periods of access. It does not charge the card automatically each month. Customers renew through another Mada payment. Automatic recurring charging requires a separately approved tokenization or recurring-payment setup and additional billing logic.

## Professional Library Dashboard Update

This edition includes the BuildQuality digital-library interface shown in the approved design:

- Dashboard summary cards and resource collections.
- Permanent sidebar sections: Codes, Materials, Quality Document Template, Method Statement, Test Reports, and Batch Plant.
- Search and category browsing.
- Responsive mobile sidebar.
- Resource previews, featured resources, popular codes, and recent additions.
- Only administrators can add, edit, or delete resources. These permissions are enforced on the Flask routes using `@admin_required`, not only hidden in the interface.
- Subscribers and users in the one-time 7-day free trial can browse and open resources.
- Expired users are redirected to the Mada subscription page.
- Existing users, links, payments, subscriptions, and trial dates remain in the same database.

### Render start command

```bash
gunicorn server:app
```
