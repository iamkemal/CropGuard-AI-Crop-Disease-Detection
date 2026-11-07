import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from werkzeug.security import generate_password_hash

from app import create_app


class AdminConsoleTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.temporary_path = Path(temporary_directory.name)
        self.database_path = self.temporary_path / "test.sqlite3"
        self.upload_path = self.temporary_path / "uploads"
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key-not-for-production",
                "DATABASE": str(self.database_path),
                "UPLOAD_FOLDER": str(self.upload_path),
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        self.admin_id = self.create_user("admin@example.test", "admin")
        self.farmer_id = self.create_user("farmer@example.test", "farmer")
        self.login_admin()

    def create_user(self, email: str, role: str) -> int:
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        f"Test {role.title()}",
                        email,
                        generate_password_hash("secure-password-123"),
                        role,
                    ),
                )
                return int(cursor.lastrowid)

    def login_admin(self) -> None:
        response = self.client.post(
            "/login",
            data={
                "email": "admin@example.test",
                "password": "secure-password-123",
            },
        )
        self.assertEqual(response.status_code, 302)

    def database_row(self, query: str, values: tuple = ()):
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(query, values).fetchone()

    def database_value(self, query: str, values: tuple = ()):
        row = self.database_row(query, values)
        return row[0] if row is not None else None

    def crop_id(self, slug: str) -> int:
        return int(self.database_value("SELECT id FROM crops WHERE slug = ?", (slug,)))

    def symptom_id(self, slug: str) -> int:
        return int(
            self.database_value("SELECT id FROM symptoms WHERE slug = ?", (slug,))
        )

    def disease_id(self, slug: str) -> int:
        return int(
            self.database_value("SELECT id FROM diseases WHERE slug = ?", (slug,))
        )

    def test_all_admin_pages_render(self) -> None:
        paths = (
            "/admin/dashboard",
            "/admin/users",
            "/admin/crops",
            f"/admin/crops/{self.crop_id('maize')}/edit",
            "/admin/diseases",
            "/admin/diseases/new",
            f"/admin/diseases/{self.disease_id('early_blight')}/edit",
            "/admin/symptoms",
            "/admin/symptoms/new",
            f"/admin/symptoms/{self.symptom_id('dark_lower_leaf_spots')}/edit",
            "/admin/rules",
            "/admin/rules/new",
            "/admin/rules/1/edit",
            "/admin/treatments",
            "/admin/treatments/new",
            "/admin/treatments/1/edit",
            "/admin/diagnoses",
            "/admin/reports",
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, response.data[:500])

    def test_admin_routes_reject_anonymous_and_farmer_accounts(self) -> None:
        self.client.post("/logout")
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 302)
        farmer_client = self.app.test_client()
        farmer_client.post(
            "/login",
            data={
                "email": "farmer@example.test",
                "password": "secure-password-123",
            },
        )
        self.assertEqual(farmer_client.get("/admin/dashboard").status_code, 403)
        self.assertEqual(farmer_client.get("/admin/users").status_code, 403)

    def test_crop_can_be_created_and_deleted_but_used_crop_is_protected(self) -> None:
        response = self.client.post(
            "/admin/crops",
            data={
                "slug": "beans",
                "name": "Beans",
                "description": "A test crop.",
                "logo_filename": "maize.svg",
                "is_active": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        beans_id = int(
            self.database_value("SELECT id FROM crops WHERE slug = 'beans'")
        )
        self.assertEqual(
            self.client.post(f"/admin/crops/{beans_id}/delete").status_code,
            302,
        )
        self.assertIsNone(
            self.database_value("SELECT id FROM crops WHERE id = ?", (beans_id,))
        )

        maize_id = self.crop_id("maize")
        protected_response = self.client.post(
            f"/admin/crops/{maize_id}/delete",
            follow_redirects=True,
        )
        self.assertEqual(protected_response.status_code, 200)
        self.assertIn(b"Deactivate it instead", protected_response.data)
        self.assertIsNotNone(
            self.database_value("SELECT id FROM crops WHERE id = ?", (maize_id,))
        )

    def test_disease_symptom_rule_and_treatment_management(self) -> None:
        tomato_id = self.crop_id("tomato")
        concentric_id = self.symptom_id("concentric_rings_in_spots")
        dark_spot_id = self.symptom_id("dark_lower_leaf_spots")
        response = self.client.post(
            "/admin/diseases/new",
            data={
                "crop_id": str(tomato_id),
                "slug": "tomato_admin_test",
                "name": "Administrative Test Disease",
                "scientific_name": "",
                "description": "A test description.",
                "cause": "A test cause.",
                "is_active": "1",
                "symptom_ids": [str(concentric_id), str(dark_spot_id)],
                "key_symptom_ids": [str(concentric_id)],
            },
        )
        self.assertEqual(response.status_code, 302)
        new_disease_id = self.disease_id("tomato_admin_test")
        self.assertEqual(
            self.database_value(
                "SELECT COUNT(*) FROM disease_symptoms WHERE disease_id = ?",
                (new_disease_id,),
            ),
            2,
        )
        self.assertEqual(
            self.database_value(
                """
                SELECT is_key FROM disease_symptoms
                WHERE disease_id = ? AND symptom_id = ?
                """,
                (new_disease_id, concentric_id),
            ),
            1,
        )

        early_blight_id = self.disease_id("early_blight")
        response = self.client.post(
            "/admin/rules/new",
            data={
                "disease_id": str(early_blight_id),
                "code": "admin_test_early_blight",
                "name": "Admin test rule",
                "description": "IF rings AND spots THEN Early Blight.",
                "minimum_matches": "2",
                "minimum_score": "0.5",
                "priority": "100",
                "required_symptoms": [str(concentric_id)],
                "supporting_symptoms": [str(dark_spot_id)],
                "is_active": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        rule_row = self.database_row(
            "SELECT id, disease_id FROM rules WHERE code = ?",
            ("admin_test_early_blight",),
        )
        self.assertEqual(rule_row["disease_id"], early_blight_id)
        self.assertEqual(
            self.database_value(
                "SELECT COUNT(*) FROM rule_conditions WHERE rule_id = ?",
                (rule_row["id"],),
            ),
            2,
        )

        maize_symptom_id = self.symptom_id("yellow_streaks_along_veins")
        invalid_rule_response = self.client.post(
            "/admin/rules/new",
            data={
                "disease_id": str(early_blight_id),
                "code": "admin_test_cross_crop",
                "name": "Invalid crop rule",
                "description": "This should not be stored.",
                "minimum_matches": "1",
                "minimum_score": "0.5",
                "priority": "100",
                "required_symptoms": [str(maize_symptom_id)],
            },
            follow_redirects=True,
        )
        self.assertEqual(invalid_rule_response.status_code, 200)
        self.assertIn(b"belonging to the selected crop", invalid_rule_response.data)
        self.assertIsNone(
            self.database_value(
                "SELECT id FROM rules WHERE code = 'admin_test_cross_crop'"
            )
        )

        response = self.client.post(
            "/admin/treatments/new",
            data={
                "disease_id": str(early_blight_id),
                "category": "prevention",
                "recommendation": "Rotate crops and remove infected residue.",
                "sort_order": "3",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.database_value(
                "SELECT COUNT(*) FROM treatments WHERE disease_id = ? AND category = 'prevention'",
                (early_blight_id,),
            ),
            2,
        )

    def test_user_management_deactivates_and_deletes_farmer(self) -> None:
        response = self.client.post(f"/admin/users/{self.farmer_id}/toggle")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.database_value(
                "SELECT is_active FROM users WHERE id = ?",
                (self.farmer_id,),
            ),
            0,
        )
        response = self.client.post(f"/admin/users/{self.farmer_id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(
            self.database_value("SELECT id FROM users WHERE id = ?", (self.farmer_id,))
        )

    def test_admin_can_review_diagnosis_and_private_image(self) -> None:
        image_name = "admin-review-test.png"
        self.upload_path.mkdir(parents=True, exist_ok=True)
        (self.upload_path / image_name).write_bytes(b"test image bytes")
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO diagnoses
                        (user_id, crop_id, image_path, outcome,
                         confidence_level, explanation)
                    VALUES (?, ?, ?, 'no_match', 'none', ?)
                    """,
                    (
                        self.farmer_id,
                        self.crop_id("tomato"),
                        image_name,
                        "No stored rule matched.",
                    ),
                )
                diagnosis_id = int(cursor.lastrowid)

        listing = self.client.get("/admin/diagnoses")
        detail = self.client.get(f"/admin/diagnoses/{diagnosis_id}")
        image = self.client.get(f"/admin/diagnoses/{diagnosis_id}/image")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(image.status_code, 200)
        self.assertIn("private", image.headers["Cache-Control"])
        image.close()

    def test_rule_with_history_is_deactivated_instead_of_deleted(self) -> None:
        rule_id = int(
            self.database_value(
                "SELECT id FROM rules WHERE code = 'tomato_early_blight'"
            )
        )
        disease_id = self.disease_id("early_blight")
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO diagnoses
                        (user_id, crop_id, outcome, confidence_level, explanation)
                    VALUES (?, ?, 'matched', 'moderate', ?)
                    """,
                    (
                        self.farmer_id,
                        self.crop_id("tomato"),
                        "Possible early blight.",
                    ),
                )
                diagnosis_id = int(cursor.lastrowid)
                connection.execute(
                    """
                    INSERT INTO diagnosis_candidates
                        (diagnosis_id, disease_id, rank, match_score,
                         confidence_level, matched_rule_codes, explanation)
                    VALUES (?, ?, 1, 0.75, 'moderate', ?, ?)
                    """,
                    (
                        diagnosis_id,
                        disease_id,
                        "tomato_early_blight",
                        "Matched symptoms and weighted coverage.",
                    ),
                )

        response = self.client.post(
            f"/admin/rules/{rule_id}/delete",
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"deactivated to preserve", response.data)
        self.assertEqual(
            self.database_value("SELECT is_active FROM rules WHERE id = ?", (rule_id,)),
            0,
        )
        farmer_client = self.app.test_client()
        farmer_client.post(
            "/login",
            data={
                "email": "farmer@example.test",
                "password": "secure-password-123",
            },
        )
        history_response = farmer_client.get(f"/farmer/diagnoses/{diagnosis_id}")
        self.assertEqual(history_response.status_code, 200)
        self.assertIn(b"Possible early blight.", history_response.data)

    def test_reports_render_database_counts(self) -> None:
        response = self.client.get("/admin/reports")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Candidate disease mentions", response.data)
        self.assertIn(b"Maize", response.data)


if __name__ == "__main__":
    unittest.main()
