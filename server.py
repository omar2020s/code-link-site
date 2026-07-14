import json
import math
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import func, or_, text
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


# =========================
# Configuration helpers
# =========================
def utcnow() -> datetime:
    """Return a naive UTC datetime suitable for SQLAlchemy DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def normalize_database_url(database_url: str) -> str:
    database_url = database_url or "sqlite:///local_links.db"

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)

    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return database_url


def subscription_plans() -> dict:
    return {
        "monthly": {
            "code": "monthly",
            "name": "Monthly Subscription",
            "price_halalas": env_int("MONTHLY_PRICE_HALALAS", 4900),
            "days": env_int("MONTHLY_SUBSCRIPTION_DAYS", 30),
            "badge": "Most Flexible",
        },
        "yearly": {
            "code": "yearly",
            "name": "Annual Subscription",
            "price_halalas": env_int("YEARLY_PRICE_HALALAS", 49000),
            "days": env_int("YEARLY_SUBSCRIPTION_DAYS", 365),
            "badge": "Best Value",
        },
    }


def money_sar(halalas: int) -> str:
    return f"SAR {halalas / 100:,.2f}"


# =========================
# Database models
# =========================
class User(UserMixin, db.Model):
    __tablename__ = "app_user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    account_enabled = db.Column(db.Boolean, nullable=False, default=True)
    subscription_status = db.Column(db.String(30), nullable=False, default="inactive")
    subscription_start = db.Column(db.DateTime, nullable=True)
    subscription_end = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    payments = db.relationship("Payment", backref="user", lazy=True)

    @property
    def is_active(self) -> bool:
        return bool(self.account_enabled)

    @property
    def has_active_subscription(self) -> bool:
        if self.is_admin:
            return True
        return bool(
            self.subscription_status == "active"
            and self.subscription_end
            and self.subscription_end > utcnow()
        )

    @property
    def subscription_days_left(self) -> int:
        if self.is_admin:
            return 999999
        if not self.subscription_end:
            return 0
        seconds = (self.subscription_end - utcnow()).total_seconds()
        return max(0, math.ceil(seconds / 86400))

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class LinkItem(db.Model):
    __tablename__ = "link_item"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    category = db.Column(db.String(150), nullable=False, index=True)
    url = db.Column(db.Text, nullable=False)
    tags = db.Column(db.String(300), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    @property
    def short_url(self) -> str:
        value = (self.url or "").replace("https://", "").replace("http://", "")
        return value[:65] + "..." if len(value) > 65 else value


class PendingCheckout(db.Model):
    __tablename__ = "pending_checkout"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(100), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("app_user.id"), nullable=False, index=True)
    plan_code = db.Column(db.String(30), nullable=False)
    amount_halalas = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="SAR")
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class Payment(db.Model):
    __tablename__ = "payment"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(30), nullable=False, default="moyasar")
    provider_payment_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("app_user.id"), nullable=False, index=True)
    plan_code = db.Column(db.String(30), nullable=False)
    amount_halalas = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="SAR")
    status = db.Column(db.String(30), nullable=False)
    provider_message = db.Column(db.String(500), nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


# =========================
# Authentication / access
# =========================
@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def is_safe_next_url(target: str) -> bool:
    if not target:
        return False
    host_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in {"http", "https"} and host_url.netloc == test_url.netloc


def subscription_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        if not current_user.has_active_subscription:
            flash("An active subscription is required to access the content library.", "warning")
            return redirect(url_for("subscribe"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


# =========================
# App helpers
# =========================
def normalize_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if value.lower().startswith(("http://", "https://")):
        return value
    if "." in value and " " not in value:
        return "https://" + value
    return value


def split_search_terms(search_text: str) -> list[str]:
    search_text = (search_text or "").strip()
    if not search_text:
        return []

    parts = re.split(r"\s*(?:-|,|/|\\|;|\+)\s*", search_text)
    terms = []
    seen = set()
    for part in parts:
        value = part.strip()
        key = value.lower()
        if value and key not in seen:
            terms.append(value)
            seen.add(key)
    return terms


def get_categories() -> list[str]:
    return [
        row[0]
        for row in db.session.query(LinkItem.category)
        .filter(LinkItem.category.isnot(None))
        .filter(LinkItem.category != "")
        .distinct()
        .order_by(LinkItem.category.asc())
        .all()
    ]


def get_dashboard_stats() -> dict:
    total_links = LinkItem.query.count()
    total_categories = (
        db.session.query(func.count(func.distinct(LinkItem.category)))
        .filter(LinkItem.category.isnot(None))
        .filter(LinkItem.category != "")
        .scalar()
        or 0
    )
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
        "category_rows": category_rows,
    }


def ensure_database_schema() -> None:
    """Create all new tables and preserve the existing link_item data."""
    db.create_all()

    # Keep compatibility with old PostgreSQL deployments of link_item.
    if db.engine.url.get_backend_name().startswith("postgresql"):
        statements = [
            "ALTER TABLE link_item ADD COLUMN IF NOT EXISTS title VARCHAR(220)",
            "ALTER TABLE link_item ADD COLUMN IF NOT EXISTS category VARCHAR(150)",
            "ALTER TABLE link_item ADD COLUMN IF NOT EXISTS url TEXT",
            "ALTER TABLE link_item ADD COLUMN IF NOT EXISTS tags VARCHAR(300)",
            "ALTER TABLE link_item ADD COLUMN IF NOT EXISTS notes TEXT",
            "ALTER TABLE link_item ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        ]
        for statement in statements:
            db.session.execute(text(statement))
        db.session.commit()


def create_or_promote_admin_from_env() -> None:
    email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD") or ""
    name = (os.environ.get("ADMIN_NAME") or "Site Administrator").strip()

    if not email or not password:
        return
    if len(password) < 8:
        print("WARNING: ADMIN_PASSWORD must contain at least 8 characters.")
        return

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(name=name, email=email, is_admin=True, account_enabled=True)
        user.set_password(password)
        db.session.add(user)
    else:
        user.is_admin = True
        user.account_enabled = True
        if env_bool("RESET_ADMIN_PASSWORD", False):
            user.set_password(password)
    db.session.commit()


def external_url(endpoint: str, **values) -> str:
    configured_base = (os.environ.get("APP_BASE_URL") or "").strip().rstrip("/")
    path = url_for(endpoint, _external=False, **values)
    if configured_base:
        return configured_base + path
    return url_for(endpoint, _external=True, _scheme="https" if request.is_secure else "http", **values)


def fetch_moyasar_payment(payment_id: str) -> dict:
    secret_key = (os.environ.get("MOYASAR_SECRET_KEY") or "").strip()
    if not secret_key:
        raise RuntimeError("MOYASAR_SECRET_KEY is not configured")

    response = requests.get(
        f"https://api.moyasar.com/v1/payments/{payment_id}",
        auth=(secret_key, ""),
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def activate_subscription(user: User, plan: dict) -> None:
    now = utcnow()
    was_active = user.has_active_subscription
    base = user.subscription_end if was_active and user.subscription_end else now

    if not was_active:
        user.subscription_start = now
    user.subscription_end = base + timedelta(days=plan["days"])
    user.subscription_status = "active"


# =========================
# App factory
# =========================
def create_app(test_config: dict | None = None) -> Flask:
    project_root = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-this-secret-key"),
        SQLALCHEMY_DATABASE_URI=normalize_database_url(
            os.environ.get("DATABASE_URL", "sqlite:///local_links.db")
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        WTF_CSRF_TIME_LIMIT=3600,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=env_bool("COOKIE_SECURE", False),
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_SECURE=env_bool("COOKIE_SECURE", False),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "warning"

    with app.app_context():
        ensure_database_schema()
        create_or_promote_admin_from_env()

    @app.before_request
    def enforce_enabled_account():
        if current_user.is_authenticated and not current_user.account_enabled:
            logout_user()
            flash("This account has been disabled. Please contact the site administrator.", "danger")
            return redirect(url_for("login"))
        return None

    register_routes(app)

    @app.context_processor
    def inject_globals():
        return {
            "plans": subscription_plans(),
            "money_sar": money_sar,
            "now_utc": utcnow(),
        }

    return app


# =========================
# Routes
# =========================
def register_routes(app: Flask) -> None:
    @app.route("/")
    def landing():
        if current_user.is_authenticated:
            if current_user.has_active_subscription:
                return redirect(url_for("library"))
            return redirect(url_for("subscribe"))
        return render_template("landing.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("landing"))

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            password_confirm = request.form.get("password_confirm", "")

            if len(name) < 2:
                flash("Please enter a valid name.", "danger")
            elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                flash("Please enter a valid email address.", "danger")
            elif len(password) < 8:
                flash("The password must contain at least 8 characters.", "danger")
            elif password != password_confirm:
                flash("The passwords do not match.", "danger")
            elif User.query.filter(func.lower(User.email) == email).first():
                flash("This email address is already registered. Please sign in instead.", "warning")
            else:
                user = User(name=name, email=email)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                login_user(user, remember=True)
                flash("Your account has been created. Choose a subscription plan to unlock the library.", "success")
                return redirect(url_for("subscribe"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("landing"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter(func.lower(User.email) == email).first()

            if not user or not user.check_password(password):
                flash("Incorrect email address or password.", "danger")
            elif not user.account_enabled:
                flash("This account is disabled. Please contact the site administrator.", "danger")
            else:
                user.last_login_at = utcnow()
                db.session.commit()
                login_user(user, remember=bool(request.form.get("remember")))
                next_url = request.args.get("next", "")
                if is_safe_next_url(next_url):
                    return redirect(next_url)
                return redirect(url_for("library" if user.has_active_subscription else "subscribe"))

        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    def logout():
        logout_user()
        flash("You have been signed out.", "success")
        return redirect(url_for("landing"))

    @app.route("/subscribe")
    def subscribe():
        if not current_user.is_authenticated:
            return redirect(url_for("login", next=url_for("subscribe")))
        return render_template(
            "subscribe.html",
            configured=bool(
                (os.environ.get("MOYASAR_PUBLISHABLE_KEY") or "").strip()
                and (os.environ.get("MOYASAR_SECRET_KEY") or "").strip()
            ),
        )

    @app.route("/checkout/<plan_code>")
    def checkout(plan_code: str):
        if not current_user.is_authenticated:
            return redirect(url_for("login", next=request.path))

        plan = subscription_plans().get(plan_code)
        if not plan:
            abort(404)

        publishable_key = (os.environ.get("MOYASAR_PUBLISHABLE_KEY") or "").strip()
        secret_key = (os.environ.get("MOYASAR_SECRET_KEY") or "").strip()
        if not publishable_key or not secret_key:
            flash("The payment gateway is not configured yet. Add your Moyasar API keys to the environment variables.", "danger")
            return redirect(url_for("subscribe"))

        pending = PendingCheckout(
            token=secrets.token_urlsafe(32),
            user_id=current_user.id,
            plan_code=plan_code,
            amount_halalas=plan["price_halalas"],
            currency="SAR",
            expires_at=utcnow() + timedelta(hours=2),
        )
        db.session.add(pending)
        db.session.commit()

        callback_url = external_url("payment_callback", token=pending.token)
        form_version = (os.environ.get("MOYASAR_FORM_VERSION") or "1.12.0").strip()

        return render_template(
            "checkout.html",
            plan=plan,
            pending=pending,
            callback_url=callback_url,
            publishable_key=publishable_key,
            form_version=form_version,
        )

    @app.route("/payment/callback/<token>")
    def payment_callback(token: str):
        if not current_user.is_authenticated:
            flash("Sign in with the account that started this payment.", "warning")
            return redirect(url_for("login", next=request.full_path.rstrip("?")))

        pending = PendingCheckout.query.filter_by(token=token).first_or_404()
        if pending.user_id != current_user.id:
            abort(403)
        if pending.expires_at < utcnow() and not pending.consumed_at:
            flash("This checkout session has expired. Please start a new payment.", "danger")
            return redirect(url_for("subscribe"))

        payment_id = (request.args.get("id") or "").strip()
        try:
            uuid.UUID(payment_id)
        except (ValueError, AttributeError):
            flash("A valid payment ID was not received.", "danger")
            return redirect(url_for("subscribe"))

        existing = Payment.query.filter_by(provider_payment_id=payment_id).first()
        if existing:
            if existing.user_id == current_user.id and existing.status == "paid":
                pending.consumed_at = pending.consumed_at or utcnow()
                db.session.commit()
                flash("This payment was already recorded and your subscription is active.", "success")
                return redirect(url_for("account"))
            flash("This payment cannot be used.", "danger")
            return redirect(url_for("subscribe"))

        try:
            payment_data = fetch_moyasar_payment(payment_id)
        except requests.RequestException:
            app.logger.exception("Failed to verify Moyasar payment")
            flash("The payment could not be verified right now. Please try the return link again.", "danger")
            return redirect(url_for("subscribe"))
        except RuntimeError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("subscribe"))

        metadata = payment_data.get("metadata") or {}
        source = payment_data.get("source") or {}
        expected_plan = subscription_plans().get(pending.plan_code)
        valid = all(
            [
                payment_data.get("status") == "paid",
                int(payment_data.get("amount") or 0) == pending.amount_halalas,
                str(payment_data.get("currency") or "").upper() == pending.currency,
                str(metadata.get("user_id") or "") == str(current_user.id),
                str(metadata.get("plan_code") or "") == pending.plan_code,
                str(metadata.get("checkout_token") or "") == pending.token,
                str(source.get("type") or "").lower() == "creditcard",
                str(source.get("company") or "").lower() == "mada",
                expected_plan is not None,
            ]
        )

        if not valid:
            app.logger.warning(
                "Rejected payment verification: %s",
                json.dumps(
                    {
                        "payment_id": payment_id,
                        "status": payment_data.get("status"),
                        "amount": payment_data.get("amount"),
                        "currency": payment_data.get("currency"),
                        "metadata": metadata,
                        "source_type": source.get("type"),
                        "card_network": source.get("company"),
                    },
                    ensure_ascii=False,
                ),
            )
            flash("The payment was rejected because its details do not match the subscription checkout.", "danger")
            return redirect(url_for("subscribe"))

        try:
            activate_subscription(current_user, expected_plan)
            payment = Payment(
                provider="moyasar",
                provider_payment_id=payment_id,
                user_id=current_user.id,
                plan_code=pending.plan_code,
                amount_halalas=pending.amount_halalas,
                currency=pending.currency,
                status="paid",
                provider_message=str(source.get("message") or payment_data.get("message") or "")[:500],
                paid_at=utcnow(),
            )
            pending.consumed_at = utcnow()
            db.session.add(payment)
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Failed to activate subscription")
            flash("Payment was received, but the subscription could not be activated. Contact support with the payment ID.", "danger")
            return redirect(url_for("subscribe"))

        flash("Mada payment verified. Your subscription is now active.", "success")
        return redirect(url_for("library"))

    @app.route("/account")
    def account():
        if not current_user.is_authenticated:
            return redirect(url_for("login", next=request.path))
        payments = (
            Payment.query.filter_by(user_id=current_user.id)
            .order_by(Payment.created_at.desc())
            .limit(50)
            .all()
        )
        return render_template("account.html", payments=payments)

    @app.route("/account/password", methods=["POST"])
    def change_password():
        if not current_user.is_authenticated:
            return redirect(url_for("login"))

        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("new_password_confirm", "")

        if not current_user.check_password(current_password):
            flash("The current password is incorrect.", "danger")
        elif len(new_password) < 8:
            flash("The new password must contain at least 8 characters.", "danger")
        elif new_password != confirm:
            flash("The new passwords do not match.", "danger")
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Your password has been changed.", "success")
        return redirect(url_for("account"))

    @app.route("/library")
    @subscription_required
    def library():
        search = request.args.get("search", "").strip()
        selected_category = request.args.get("category", "").strip()
        search_terms = split_search_terms(search)
        categories = get_categories()
        stats = get_dashboard_stats()
        table_ready = bool(selected_category or search_terms)
        links = []

        if table_ready:
            query = LinkItem.query
            if selected_category:
                query = query.filter(LinkItem.category == selected_category)
            if search_terms:
                search_filters = []
                for term in search_terms:
                    like_text = f"%{term}%"
                    search_filters.extend(
                        [
                            LinkItem.title.ilike(like_text),
                            LinkItem.category.ilike(like_text),
                            LinkItem.tags.ilike(like_text),
                            LinkItem.notes.ilike(like_text),
                            LinkItem.url.ilike(like_text),
                        ]
                    )
                query = query.filter(or_(*search_filters))
            links = query.order_by(LinkItem.created_at.desc(), LinkItem.title.asc()).all()

        return render_template(
            "index.html",
            links=links,
            categories=categories,
            selected_category=selected_category,
            search=search,
            stats=stats,
            table_ready=table_ready,
            edit_link=None,
        )

    @app.route("/link/save", methods=["POST"])
    @admin_required
    def save_link():
        link_id = request.form.get("link_id", "").strip()
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        url = normalize_url(request.form.get("url", ""))
        tags = request.form.get("tags", "").strip()
        notes = request.form.get("notes", "").strip()

        if not title or not category or not url:
            flash("Title, category, and URL are required.", "danger")
            return redirect(url_for("library"))
        if not url.lower().startswith(("http://", "https://")):
            flash("Enter a valid URL beginning with https://", "danger")
            return redirect(url_for("library"))

        try:
            if link_id:
                link = db.get_or_404(LinkItem, int(link_id))
                link.title = title
                link.category = category
                link.url = url
                link.tags = tags
                link.notes = notes
                flash("The link has been updated.", "success")
            else:
                db.session.add(
                    LinkItem(
                        title=title,
                        category=category,
                        url=url,
                        tags=tags,
                        notes=notes,
                    )
                )
                flash("The link has been added.", "success")
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            app.logger.exception("Link save failed")
            flash(f"The link could not be saved: {exc}", "danger")

        return redirect(url_for("library", category=category))

    @app.route("/link/<int:link_id>/edit")
    @admin_required
    def edit_link(link_id: int):
        item = db.get_or_404(LinkItem, link_id)
        categories = get_categories()
        selected_category = item.category or ""
        links = (
            LinkItem.query.filter(LinkItem.category == selected_category)
            .order_by(LinkItem.created_at.desc(), LinkItem.title.asc())
            .all()
        )
        return render_template(
            "index.html",
            links=links,
            categories=categories,
            selected_category=selected_category,
            search="",
            stats=get_dashboard_stats(),
            table_ready=True,
            edit_link=item,
        )

    @app.route("/link/<int:link_id>/delete", methods=["POST"])
    @admin_required
    def delete_link(link_id: int):
        link = db.get_or_404(LinkItem, link_id)
        selected_category = link.category or ""
        try:
            db.session.delete(link)
            db.session.commit()
            flash("The link has been deleted.", "success")
        except Exception as exc:
            db.session.rollback()
            flash(f"The link could not be deleted: {exc}", "danger")
        return redirect(url_for("library", category=selected_category))

    @app.route("/link/<int:link_id>/open")
    @subscription_required
    def open_link(link_id: int):
        link = db.get_or_404(LinkItem, link_id)
        return redirect(link.url)

    @app.route("/admin/users")
    @admin_required
    def admin_users():
        search = request.args.get("search", "").strip()
        query = User.query
        if search:
            like = f"%{search}%"
            query = query.filter(or_(User.name.ilike(like), User.email.ilike(like)))
        users = query.order_by(User.created_at.desc()).all()
        payments = Payment.query.order_by(Payment.created_at.desc()).limit(100).all()
        return render_template("admin_users.html", users=users, payments=payments, search=search)

    @app.route("/admin/users/<int:user_id>/activate", methods=["POST"])
    @admin_required
    def admin_activate_user(user_id: int):
        user = db.get_or_404(User, user_id)
        try:
            days = int(request.form.get("days", "30"))
        except ValueError:
            days = 30
        days = max(1, min(days, 3650))

        now = utcnow()
        base = user.subscription_end if user.subscription_end and user.subscription_end > now else now
        if not user.subscription_start or user.subscription_end is None or user.subscription_end <= now:
            user.subscription_start = now
        user.subscription_end = base + timedelta(days=days)
        user.subscription_status = "active"
        user.account_enabled = True
        db.session.commit()
        flash(f"Subscription activated for {user.name} for {days} days.", "success")
        return redirect(url_for("admin_users"))

    @app.route("/admin/users/<int:user_id>/revoke", methods=["POST"])
    @admin_required
    def admin_revoke_user(user_id: int):
        user = db.get_or_404(User, user_id)
        if user.is_admin:
            flash("An administrator account always has access and cannot have its subscription revoked.", "warning")
        else:
            user.subscription_status = "inactive"
            user.subscription_end = utcnow()
            db.session.commit()
            flash("The subscription has been revoked.", "success")
        return redirect(url_for("admin_users"))

    @app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
    @admin_required
    def admin_toggle_user(user_id: int):
        user = db.get_or_404(User, user_id)
        if user.id == current_user.id:
            flash("You cannot disable your own administrator account.", "warning")
        else:
            user.account_enabled = not user.account_enabled
            db.session.commit()
            flash("The account status has been updated.", "success")
        return redirect(url_for("admin_users"))

    @app.route("/terms")
    def terms():
        return render_template("terms.html")

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.route("/health")
    def health():
        return {"status": "ok", "app": "paid-link-library"}

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=env_bool("FLASK_DEBUG", False),
    )
