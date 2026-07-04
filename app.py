import os
import re
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, text, func


db = SQLAlchemy()


# ================= DATABASE CONFIG =================
def normalize_database_url(database_url: str) -> str:
    """
    Render may provide:
    postgres://...
    or
    postgresql://...

    This app uses psycopg v3, so the final SQLAlchemy URI should be:
    postgresql+psycopg://...
    """
    database_url = database_url or "sqlite:///local_links.db"

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)

    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return database_url


# ================= MODELS =================
class LinkItem(db.Model):
    __tablename__ = "link_item"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    category = db.Column(db.String(150), nullable=False, index=True)
    url = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def short_url(self):
        value = (self.url or "").replace("https://", "").replace("http://", "")
        return value[:70] + "..." if len(value) > 70 else value


# ================= APP FACTORY =================
def create_app():
    project_root = Path(__file__).resolve().parent

    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )

    app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

    database_url = normalize_database_url(
        os.environ.get("DATABASE_URL", "sqlite:///local_links.db")
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        ensure_database_schema()

    register_routes(app)

    return app


# ================= DATABASE SCHEMA =================
def ensure_database_schema():
    """
    Create/update database safely.
    This does not delete saved links.
    """
    db.create_all()

    # Extra safety for PostgreSQL if table already exists and columns are missing.
    if db.engine.url.get_backend_name().startswith("postgresql"):
        statements = [
            "ALTER TABLE link_item ADD COLUMN IF NOT EXISTS title VARCHAR(220)",
            "ALTER TABLE link_item ADD COLUMN IF NOT EXISTS category VARCHAR(150)",
            "ALTER TABLE link_item ADD COLUMN IF NOT EXISTS url TEXT",
            "ALTER TABLE link_item ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE link_item ADD COLUMN IF NOT EXISTS tags VARCHAR(300)",
            "ALTER TABLE link_item ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        ]

        for statement in statements:
            db.session.execute(text(statement))

        db.session.commit()


# ================= HELPERS =================
def normalize_url(value: str) -> str:
    value = (value or "").strip()

    if not value:
        return ""

    if value.lower().startswith(("http://", "https://")):
        return value

    # If user writes google.com or www.google.com
    if "." in value and " " not in value:
        return "https://" + value

    return value


def clean_list(values):
    clean = []
    seen = set()

    for value in values:
        value = (value or "").strip()
        key = value.lower()

        if value and key not in seen:
            clean.append(value)
            seen.add(key)

    return clean


def split_search_terms(search_text: str):
    """
    Allows searching by several keywords.
    Examples:
    concrete - repair
    aramco, mot
    datasheet / epoxy
    """
    search_text = (search_text or "").strip()

    if not search_text:
        return []

    parts = re.split(r"\s*(?:-|,|/|\\|;|،|؛|\+)\s*", search_text)

    terms = []
    seen = set()

    for part in parts:
        value = part.strip()
        key = value.lower()

        if value and key not in seen:
            terms.append(value)
            seen.add(key)

    return terms


def get_categories():
    return [
        row[0]
        for row in db.session.query(LinkItem.category)
        .filter(LinkItem.category.isnot(None))
        .filter(LinkItem.category != "")
        .distinct()
        .order_by(LinkItem.category.asc())
        .all()
    ]


def get_dashboard_stats():
    total_links = LinkItem.query.count()

    total_categories = (
        db.session.query(func.count(func.distinct(LinkItem.category)))
        .filter(LinkItem.category.isnot(None))
        .filter(LinkItem.category != "")
        .scalar()
        or 0
    )

    last_link = LinkItem.query.order_by(LinkItem.created_at.desc()).first()

    category_rows = (
        db.session.query(LinkItem.category, func.count(LinkItem.id))
        .filter(LinkItem.category.isnot(None))
        .filter(LinkItem.category != "")
        .group_by(LinkItem.category)
        .order_by(LinkItem.category.asc())
        .all()
    )

    return {
        "total_links": total_links,
        "total_categories": total_categories,
        "last_link": last_link.title if last_link else "-",
        "category_rows": category_rows,
    }


# ================= ROUTES =================
def register_routes(app):
    @app.route("/", methods=["GET"])
    def index():
        search = request.args.get("search", "").strip()
        selected_categories = clean_list(request.args.getlist("categories"))
        search_terms = split_search_terms(search)

        categories = get_categories()
        stats = get_dashboard_stats()

        query = LinkItem.query

        if selected_categories:
            query = query.filter(LinkItem.category.in_(selected_categories))

        if search_terms:
            search_filters = []

            for term in search_terms:
                like_text = f"%{term}%"
                search_filters.extend([
                    LinkItem.title.ilike(like_text),
                    LinkItem.category.ilike(like_text),
                    LinkItem.description.ilike(like_text),
                    LinkItem.tags.ilike(like_text),
                    LinkItem.url.ilike(like_text),
                ])

            query = query.filter(or_(*search_filters))

        links = query.order_by(LinkItem.created_at.desc(), LinkItem.title.asc()).all()

        return render_template(
            "index.html",
            links=links,
            categories=categories,
            selected_categories=selected_categories,
            search=search,
            search_terms=search_terms,
            stats=stats,
            edit_link=None,
        )

    @app.route("/link/save", methods=["POST"])
    def save_link():
        link_id = request.form.get("link_id", "").strip()
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        url = normalize_url(request.form.get("url", ""))
        description = request.form.get("description", "").strip()
        tags = request.form.get("tags", "").strip()

        if not title:
            flash("Link title is required.", "danger")
            return redirect(url_for("index"))

        if not category:
            flash("Category is required to keep your links organized.", "warning")
            return redirect(url_for("index"))

        if not url:
            flash("URL is required.", "danger")
            return redirect(url_for("index"))

        if not url.lower().startswith(("http://", "https://")):
            flash("Please enter a valid link like https://example.com", "danger")
            return redirect(url_for("index"))

        try:
            if link_id:
                link = LinkItem.query.get_or_404(int(link_id))
                link.title = title
                link.category = category
                link.url = url
                link.description = description
                link.tags = tags
                flash("Link updated successfully.", "success")
            else:
                link = LinkItem(
                    title=title,
                    category=category,
                    url=url,
                    description=description,
                    tags=tags,
                )
                db.session.add(link)
                flash("Link added successfully.", "success")

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            flash(f"Database error: {e}", "danger")

        return redirect(url_for("index", categories=[category]))

    @app.route("/edit/<int:link_id>")
    def edit_link(link_id):
        edit_link_item = LinkItem.query.get_or_404(link_id)

        categories = get_categories()
        stats = get_dashboard_stats()
        selected_categories = [edit_link_item.category] if edit_link_item.category else []

        links = (
            LinkItem.query.filter(LinkItem.category.in_(selected_categories))
            .order_by(LinkItem.created_at.desc(), LinkItem.title.asc())
            .all()
            if selected_categories
            else []
        )

        return render_template(
            "index.html",
            links=links,
            categories=categories,
            selected_categories=selected_categories,
            search="",
            search_terms=[],
            stats=stats,
            edit_link=edit_link_item,
        )

    @app.route("/delete/<int:link_id>", methods=["GET", "POST"])
    def delete_link(link_id):
        link = LinkItem.query.get_or_404(link_id)
        selected_category = link.category or ""

        try:
            db.session.delete(link)
            db.session.commit()
            flash("Link deleted successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Delete failed: {e}", "danger")

        return redirect(
            url_for("index", categories=[selected_category] if selected_category else [])
        )

    @app.route("/open/<int:link_id>")
    def open_link(link_id):
        link = LinkItem.query.get_or_404(link_id)
        return redirect(link.url)

    @app.route("/health")
    def health():
        return {"status": "ok", "app": "link-manager"}

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True,
    )
