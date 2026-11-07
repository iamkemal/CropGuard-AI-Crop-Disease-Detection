"""Exercise authentication, account provisioning, sessions, and CSRF checks."""

import sqlite3
import unittest
from contextlib import closing

from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app
from tests.support import FlaskTestCase


class AuthenticationTests(FlaskTestCase):
    """Verify registration, login, authorization, and administrator provisioning."""
    def create_user(
        self,
        email: str = "farmer@example.test",
        role: str = "farmer",
        is_active: int = 1,
    ) -> int:
        """Insert a test user with a hashed password into the isolated database."""
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role, is_active)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "Test User",
                        email,
                        generate_password_hash("secure-password-123"),
                        role,
                        is_active,
                    ),
                )
                return int(cursor.lastrowid)

    def test_registration_creates_farmer_with_hashed_password(self) -> None:
        """Verify registration creates a farmer and hashes the supplied password."""
        response = self.client.post(
            "/register",
            data={
                "username": "Amina Farmer",
                "email": "amina@example.test",
                "password": "secure-password-123",
                "confirm_password": "secure-password-123",
            },
        )

        self.assertEqual(response.status_code, 302)
        with closing(sqlite3.connect(self.database_path)) as connection:
            user = connection.execute(
                "SELECT password_hash, role FROM users WHERE email = ?",
                ("amina@example.test",),
            ).fetchone()
        self.assertEqual(user[1], "farmer")
        self.assertNotEqual(user[0], "secure-password-123")
        self.assertTrue(check_password_hash(user[0], "secure-password-123"))

    def test_registration_rejects_duplicate_email_case_insensitively(self) -> None:
        """Verify account email uniqueness is enforced without case sensitivity."""
        self.create_user(email="farmer@example.test")
        response = self.client.post(
            "/register",
            data={
                "username": "Another Farmer",
                "email": "FARMER@example.test",
                "password": "secure-password-123",
                "confirm_password": "secure-password-123",
            },
        )

        self.assertEqual(response.status_code, 400)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                1,
            )

    def test_login_and_logout_use_post_for_session_changes(self) -> None:
        """Verify login establishes a session and POST logout removes it."""
        self.create_user()
        login_response = self.client.post(
            "/login",
            data={
                "email": "farmer@example.test",
                "password": "secure-password-123",
            },
        )

        self.assertEqual(login_response.status_code, 302)
        self.assertIn("/farmer/dashboard", login_response.headers["Location"])
        with self.client.session_transaction() as browser_session:
            self.assertTrue(browser_session.permanent)
            self.assertIn("user_id", browser_session)

        logout_response = self.client.post("/logout")
        self.assertEqual(logout_response.status_code, 302)
        with self.client.session_transaction() as browser_session:
            self.assertNotIn("user_id", browser_session)

    def test_login_rejects_inactive_accounts(self) -> None:
        """Verify inactive accounts cannot establish authenticated sessions."""
        self.create_user(is_active=0)
        response = self.client.post(
            "/login",
            data={
                "email": "farmer@example.test",
                "password": "secure-password-123",
            },
        )

        self.assertEqual(response.status_code, 401)
        with self.client.session_transaction() as browser_session:
            self.assertNotIn("user_id", browser_session)

    def test_roles_protect_dashboards(self) -> None:
        """Verify farmer sessions cannot access the administrator dashboard."""
        self.create_user()
        response = self.client.get("/admin/dashboard")
        self.assertEqual(response.status_code, 302)

        self.client.post(
            "/login",
            data={
                "email": "farmer@example.test",
                "password": "secure-password-123",
            },
        )
        response = self.client.get("/admin/dashboard")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/farmer/dashboard").status_code, 200)

    def test_admin_can_access_admin_dashboard_but_not_farmer_dashboard(self) -> None:
        """Verify administrator sessions are restricted to their own role views."""
        self.create_user(email="admin@example.test", role="admin")
        self.client.post(
            "/login",
            data={
                "email": "admin@example.test",
                "password": "secure-password-123",
            },
        )

        self.assertEqual(self.client.get("/admin/dashboard").status_code, 200)
        self.assertEqual(self.client.get("/farmer/dashboard").status_code, 403)

    def test_create_admin_cli_provisions_hashed_admin_account(self) -> None:
        """Verify the CLI creates an administrator with a hashed password."""
        result = self.app.test_cli_runner().invoke(
            args=["create-admin"],
            input=(
                "System Admin\n"
                "admin@example.test\n"
                "Excellent Admin Pass 123!\n"
                "Excellent Admin Pass 123!\n"
            ),
        )

        self.assertEqual(result.exit_code, 0, result.output)
        with closing(sqlite3.connect(self.database_path)) as connection:
            user = connection.execute(
                "SELECT password_hash, role FROM users WHERE email = ?",
                ("admin@example.test",),
            ).fetchone()
        self.assertEqual(user[1], "admin")
        self.assertTrue(
            check_password_hash(user[0], "Excellent Admin Pass 123!")
        )

    def test_production_requires_configured_secret_key(self) -> None:
        """Verify production startup rejects a missing session-signing secret."""
        with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
            create_app(
                {
                    "APP_ENV": "production",
                    "SECRET_KEY": None,
                    "DATABASE": str(self.database_path),
                    "UPLOAD_FOLDER": str(self.temporary_path / "uploads"),
                }
            )

    def test_csrf_protects_post_routes(self) -> None:
        """Verify CSRF protection rejects a POST without a valid token."""
        csrf_app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key-not-for-production",
                "DATABASE": str(self.database_path),
                "UPLOAD_FOLDER": str(self.temporary_path / "uploads"),
                "WTF_CSRF_ENABLED": True,
            }
        )

        response = csrf_app.test_client().post(
            "/register",
            data={
                "username": "Amina Farmer",
                "email": "amina@example.test",
                "password": "secure-password-123",
                "confirm_password": "secure-password-123",
            },
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
