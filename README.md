# Code Link Site

موقع Python Flask لحفظ أي كود وإنشاء لينك مباشر له.

## Local Run

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

افتح:

```text
http://127.0.0.1:5000
```

## Render Settings

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
gunicorn app:app
```

Environment Variables:

```text
DATABASE_URL=postgresql://user:password@host:5432/dbname
SECRET_KEY=any-long-secret-key
```

## Important

الموقع يعرض الكود فقط ولا ينفذه على السيرفر.
