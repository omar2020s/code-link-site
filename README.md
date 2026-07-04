# Code Link Site

موقع بسيط بـ Python Flask يسمح لك بكتابة أي كود وحفظه، ثم يعطيك رابطًا خاصًا لمشاركته.

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

## Environment Variables on Render

- `DATABASE_URL`
- `SECRET_KEY`

## Important

الموقع يعرض الكود فقط ولا ينفذه على السيرفر.
