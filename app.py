import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, abort, Response
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def normalize_database_url(url: str) -> str:
    """
    Render أحيانًا يعطي الرابط بصيغة postgres://
    و SQLAlchemy يفضل postgresql://
    """
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class CodeSnippet(db.Model):
    __tablename__ = "code_snippets"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(32), unique=True, nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False, default="Untitled Code")
    language = db.Column(db.String(50), nullable=False, default="text")
    code = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


def create_app():
    project_root = Path(__file__).resolve().parent

    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )

    database_url = normalize_database_url(
        os.getenv("DATABASE_URL", "sqlite:///local.db")
    )

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "POST":
            title = (request.form.get("title") or "Untitled Code").strip()[:120]
            language = (request.form.get("language") or "text").strip()[:50]
            code = (request.form.get("code") or "").strip()

            if not code:
                return render_template(
                    "index.html",
                    error="اكتب الكود الأول قبل إنشاء اللينك.",
                    title_value=title,
                    language_value=language,
                    code_value=code,
                ), 400

            slug = secrets.token_urlsafe(8)
            while CodeSnippet.query.filter_by(slug=slug).first():
                slug = secrets.token_urlsafe(8)

            snippet = CodeSnippet(
                slug=slug,
                title=title,
                language=language,
                code=code,
            )

            db.session.add(snippet)
            db.session.commit()

            return redirect(url_for("view_code", slug=snippet.slug))

        return render_template("index.html")

    @app.route("/c/<slug>")
    def view_code(slug):
        snippet = CodeSnippet.query.filter_by(slug=slug).first()
        if not snippet:
            abort(404)
        return render_template("view.html", snippet=snippet)

    @app.route("/raw/<slug>")
    def raw_code(slug):
        snippet = CodeSnippet.query.filter_by(slug=slug).first()
        if not snippet:
            abort(404)

        return Response(
            snippet.code,
            mimetype="text/plain; charset=utf-8",
        )

    @app.route("/health")
    def health():
        return {"status": "ok"}

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
