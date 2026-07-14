import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("MOYASAR_PUBLISHABLE_KEY", "pk_test_example")
os.environ.setdefault("MOYASAR_SECRET_KEY", "sk_test_example")

from server import LinkItem, PendingCheckout, User, create_app, db  # noqa: E402


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

    def test_unpaid_user_is_blocked_from_library(self):
        self.register_user()
        response = self.client.get("/library", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/subscribe", response.headers["Location"])

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
    def test_verified_payment_activates_subscription(self, mock_fetch):
        self.register_user()
        with self.app.app_context():
            user = User.query.filter_by(email="user@example.com").first()
            pending = PendingCheckout(
                token="secure-token",
                user_id=user.id,
                plan_code="monthly",
                amount_halalas=4900,
                currency="SAR",
                expires_at=__import__("server").utcnow() + __import__("datetime").timedelta(hours=1),
            )
            db.session.add(pending)
            db.session.commit()
            user_id = user.id

        payment_id = "79cced57-9deb-4c4b-8f48-59c124f79688"
        mock_fetch.return_value = {
            "id": payment_id,
            "status": "paid",
            "amount": 4900,
            "currency": "SAR",
            "message": "Succeeded",
            "metadata": {
                "user_id": str(user_id),
                "plan_code": "monthly",
                "checkout_token": "secure-token",
            },
        }
        response = self.client.get(f"/payment/callback/secure-token?id={payment_id}")
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            user = db.session.get(User, user_id)
            self.assertTrue(user.has_active_subscription)


if __name__ == "__main__":
    unittest.main()
