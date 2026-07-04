# Link Library Manager

Flask + PostgreSQL app for Render.

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
DATABASE_URL=your_render_internal_database_url
SECRET_KEY=your_secret_key
```

## Important

This version forces Python 3.12.8 using `.python-version` to avoid Python 3.14 compatibility issues.
