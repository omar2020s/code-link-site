# Quality Reference Library — English + Saudi Mada Payments

A complete Flask subscription website with an English interface and Saudi Mada card payments through Moyasar.

## Main features

- Fully English user interface, messages, checkout, account pages, administration, terms, and privacy templates.
- Secure registration and sign-in with hashed passwords.
- Protected library access for active subscribers only.
- Monthly and annual subscription plans.
- Mada-only card form through Moyasar.
- Server-side verification of payment status, amount, currency, user metadata, plan, checkout token, payment uniqueness, source type, and Mada card network.
- Administrator account with permanent library access.
- Administrator controls for manual activation, revocation, and account disabling.
- Administrator-only link creation, editing, and deletion.
- Subscriber search and link opening.
- CSRF protection, secure cookies, safe redirects, and PostgreSQL support.
- Existing `link_item` records remain compatible when the same production `DATABASE_URL` is used.

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

Set environment variables, then run:

```bash
python server.py
```

Open:

```text
http://127.0.0.1:5000
```

## 2. Administrator account

Add these environment variables before starting the website:

```text
ADMIN_NAME=Site Administrator
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=StrongPassword123!
RESET_ADMIN_PASSWORD=0
```

The account is created automatically. An existing account with the same email is promoted to administrator.

To reset the administrator password, temporarily set:

```text
RESET_ADMIN_PASSWORD=1
```

Restart or redeploy the service, sign in successfully, and then return it to:

```text
RESET_ADMIN_PASSWORD=0
```

## 3. Moyasar and Mada setup

Create a Moyasar account and obtain the publishable and secret API keys. Begin with test keys:

```text
MOYASAR_PUBLISHABLE_KEY=pk_test_...
MOYASAR_SECRET_KEY=sk_test_...
APP_BASE_URL=https://your-domain.onrender.com
COOKIE_SECURE=1
```

The checkout page initializes Moyasar with:

```javascript
methods: ['creditcard'],
supported_networks: ['mada'],
language: 'en'
```

The callback then fetches the payment from Moyasar using the secret key and requires all of the following before access is activated:

```text
status = paid
amount = the selected plan price
currency = SAR
metadata user_id = signed-in user
metadata plan_code = selected plan
metadata checkout_token = pending checkout token
source.type = creditcard
source.company = mada
payment ID has not been used previously
```

Using `supported_networks: ['mada']` limits the payment form to Mada. Live Mada processing must also be enabled and approved in your Moyasar merchant account.

## 4. Database

For local development, SQLite is used automatically:

```text
DATABASE_URL=sqlite:///local_links.db
```

For production, use PostgreSQL from Supabase or Render:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/postgres
```

The code automatically converts PostgreSQL URLs to the `psycopg` SQLAlchemy driver format.

To preserve an existing library, keep the same production `DATABASE_URL`. The existing `link_item` table is retained and the account/payment tables are created alongside it.

## 5. Render deployment

Manual configuration:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn server:app
Health Check Path: /health
```

Required Render environment variables:

```text
SECRET_KEY
DATABASE_URL
APP_BASE_URL
COOKIE_SECURE=1
ADMIN_NAME
ADMIN_EMAIL
ADMIN_PASSWORD
RESET_ADMIN_PASSWORD=0
MOYASAR_PUBLISHABLE_KEY
MOYASAR_SECRET_KEY
```

After replacing the files in GitHub, use:

```text
Manual Deploy → Clear build cache & deploy
```

## 6. Prices

Prices use halalas:

```text
MONTHLY_PRICE_HALALAS=4900
MONTHLY_SUBSCRIPTION_DAYS=30
YEARLY_PRICE_HALALAS=49000
YEARLY_SUBSCRIPTION_DAYS=365
```

Examples:

```text
4900 = SAR 49.00
9900 = SAR 99.00
```

## 7. Testing

Run:

```bash
python -m unittest discover -s tests -v
```

The tests cover:

- Blocking unpaid users from the library.
- Administrator link management.
- Successful verified Mada payment activation.
- Rejection of a paid transaction from a non-Mada network.

## 8. Before accepting live payments

- Complete Moyasar merchant onboarding and ensure Mada is enabled for the live account.
- Replace test API keys with live API keys.
- Use HTTPS and set `COOKIE_SECURE=1`.
- Set `APP_BASE_URL` to the exact public HTTPS domain without a trailing slash.
- Test successful, declined, and 3-D Secure payment flows in test mode.
- Replace the starter Terms and Privacy Policy with legally reviewed business documents.
- Publish a clear refund and cancellation policy.
- Never commit `.env`, database passwords, secret keys, or live credentials to GitHub.

## Subscription behavior

This version sells fixed periods of access. A customer renews by making another Mada payment, and the new period is added to the remaining subscription time. It does not automatically charge the card every month. Automatic recurring charging requires a separately approved tokenization/recurring-payment setup and additional billing logic.
