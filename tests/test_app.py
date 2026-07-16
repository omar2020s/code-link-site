import os
import tempfile
import unittest
from datetime import timedelta
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("MOYASAR_PUBLISHABLE_KEY", "pk_test_example")
os.environ.setdefault("MOYASAR_SECRET_KEY", "sk_test_example")
os.environ.setdefault("FREE_TRIAL_DAYS", "7")

from server import (  # noqa: E402
    LinkItem,
    PendingCheckout,
    User,
    create_app,
    db,
    ensure_database_schema,
    utcnow,
)


class AppFlowTests(unittest.TestCase):
    def setUp(self):
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_file.close()
        self.app = create_app(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.db_file.name}",
                "SECRET_KEY": "test-secret",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        os.unlink(self.db_file.name)

    def register_user(self):
        return self.client.post(
            "/register",
            data={
                "name": "Test User",
                "email": "user@example.com",
                "password": "Password123!",
                "password_confirm": "Password123!",
            },
            follow_redirects=False,
        )

    def create_pending_checkout(self, token="secure-token"):
        with self.app.app_context():
            user = User.query.filter_by(email="user@example.com").first()
            pending = PendingCheckout(
                token=token,
                user_id=user.id,
                plan_code="monthly",
                amount_halalas=4900,
                currency="SAR",
                expires_at=utcnow() + timedelta(hours=1),
            )
            db.session.add(pending)
            db.session.commit()
            return user.id

    @staticmethod
    def payment_payload(payment_id, user_id, network="mada"):
        return {
            "id": payment_id,
            "status": "paid",
            "amount": 4900,
            "currency": "SAR",
            "metadata": {
                "user_id": str(user_id),
                "plan_code": "monthly",
                "checkout_token": "secure-token",
            },
            "source": {
                "type": "creditcard",
                "company": network,
                "message": "APPROVED",
                "response_code": "00",
            },
        }

    def test_new_user_receives_seven_day_trial_and_can_open_library(self):
        response = self.register_user()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/library", response.headers["Location"])

        with self.app.app_context():
            user = User.query.filter_by(email="user@example.com").first()
            self.assertTrue(user.has_active_trial)
            self.assertTrue(user.has_library_access)
            remaining = user.trial_end - user.trial_start
            self.assertGreaterEqual(remaining, timedelta(days=7) - timedelta(seconds=2))

        library_response = self.client.get("/library", follow_redirects=False)
        self.assertEqual(library_response.status_code, 200)

    def test_expired_trial_is_redirected_to_subscription(self):
        self.register_user()
        with self.app.app_context():
            user = User.query.filter_by(email="user@example.com").first()
            user.trial_end = utcnow() - timedelta(seconds=1)
            db.session.commit()

        response = self.client.get("/library", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/subscribe", response.headers["Location"])

    def test_expired_trial_is_not_reset_on_schema_check(self):
        self.register_user()
        with self.app.app_context():
            user = User.query.filter_by(email="user@example.com").first()
            expired_at = utcnow() - timedelta(days=1)
            user.trial_end = expired_at
            db.session.commit()

            ensure_database_schema()
            refreshed = db.session.get(User, user.id)
            self.assertEqual(refreshed.trial_end, expired_at)
            self.assertFalse(refreshed.has_active_trial)

    def test_admin_can_access_library_and_add_link(self):
        with self.app.app_context():
            admin = User(name="Admin", email="admin@test.com", is_admin=True)
            admin.set_password("Password123!")
            db.session.add(admin)
            db.session.commit()

        self.client.post("/login", data={"email": "admin@test.com", "password": "Password123!"})
        response = self.client.post(
            "/link/save",
            data={"title": "ACI", "category": "Codes", "url": "https://example.com"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(LinkItem.query.count(), 1)

    @patch("server.fetch_moyasar_payment")
    def test_verified_mada_payment_activates_subscription_after_trial(self, mock_fetch):
        self.register_user()
        user_id = self.create_pending_checkout()
        with self.app.app_context():
            original_trial_end = db.session.get(User, user_id).trial_end

        payment_id = "79cced57-9deb-4c4b-8f48-59c124f79688"
        mock_fetch.return_value = self.payment_payload(payment_id, user_id, network="mada")

        response = self.client.get(f"/payment/callback/secure-token?id={payment_id}")
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            user = db.session.get(User, user_id)
            self.assertTrue(user.has_active_subscription)
            self.assertGreaterEqual(
                user.subscription_end,
                original_trial_end + timedelta(days=30) - timedelta(seconds=2),
            )

    @patch("server.fetch_moyasar_payment")
    def test_non_mada_payment_is_rejected(self, mock_fetch):
        self.register_user()
        user_id = self.create_pending_checkout()
        payment_id = "4bb33a01-604b-4f80-965b-bc8cd6311b18"
        mock_fetch.return_value = self.payment_payload(payment_id, user_id, network="visa")

        response = self.client.get(f"/payment/callback/secure-token?id={payment_id}")
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            user = db.session.get(User, user_id)
            self.assertFalse(user.has_active_subscription)
            self.assertTrue(user.has_active_trial)


if __name__ == "__main__":
    unittest.main()
