# Link Library Manager

Flask + PostgreSQL app for Render.

This app allows you to:
- Add links
- Organize links by category
- Add tags and descriptions
- Search links
- Open, edit and delete links

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

## Health Check

```text
/health
```

Expected response:

```json
{"status":"ok","app":"link-manager"}
```

## Important Files

- `app.py` contains the Flask application.
- `.python-version` contains only the Python version.
- `requirements.txt` contains only Python packages.
