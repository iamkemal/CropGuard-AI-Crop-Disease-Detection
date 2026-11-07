"""Exercise diagnosis submission, history, and private upload access."""

import sqlite3
import unittest
from contextlib import closing
from io import BytesIO
from urllib.parse import urlparse

from PIL import Image
from werkzeug.security import generate_password_hash

from tests.support import FlaskTestCase


class FarmerWorkflowTests(FlaskTestCase):
    """Verify farmer diagnosis submission and ownership of stored images."""
    def setUp(self) -> None:
        super().setUp()
        self.create_user("farmer@example.test")
        self.login("farmer@example.test")

    def create_user(self, email: str) -> None:
        """Insert a test user with a hashed password into the isolated database."""
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (?, ?, ?, 'farmer')
                    """,
                    (
                        "Test Farmer",
                        email,
                        generate_password_hash("secure-password-123"),
                    ),
                )

    def login(self, email: str) -> None:
        """Log the test browser in using the specified farmer account."""
        response = self.client.post(
            "/login",
            data={
                "email": email,
                "password": "secure-password-123",
            },
        )
        self.assertEqual(response.status_code, 302)

    def create_image(self, image_format: str = "PNG") -> BytesIO:
        """Create an in-memory image for the multipart diagnosis requests."""
        image_data = BytesIO()
        Image.new("RGB", (32, 24), color=(35, 107, 69)).save(
            image_data,
            format=image_format,
        )
        image_data.seek(0)
        return image_data

    def test_crop_selection_and_diagnosis_form_show_crop_logo(self) -> None:
        """Verify crop and diagnosis pages include crop illustrations and upload guidance."""
        crop_response = self.client.get("/farmer/crops")
        diagnosis_response = self.client.get("/farmer/crops/maize")
        disease_response = self.client.get("/farmer/diseases/early_blight")

        self.assertEqual(crop_response.status_code, 200)
        self.assertIn(b"images/logos/maize.svg", crop_response.data)
        self.assertIn(b"images/logos/tomato.svg", crop_response.data)
        self.assertEqual(diagnosis_response.status_code, 200)
        self.assertIn(b"cropImagePreview", diagnosis_response.data)
        self.assertIn(b"not analyzed by the diagnosis engine", diagnosis_response.data)
        self.assertEqual(disease_response.status_code, 200)
        self.assertIn(b"Agricultural references", disease_response.data)

    def test_diagnosis_saves_symptoms_candidate_and_private_image(self) -> None:
        """Verify a submitted diagnosis stores its evidence and private photo."""
        response = self.client.post(
            "/farmer/crops/tomato",
            data={
                "symptoms": [
                    "concentric_rings_in_spots",
                    "dark_lower_leaf_spots",
                ],
                "crop_image": (self.create_image(), "field.png", "image/png"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 302)
        diagnosis_url = urlparse(response.headers["Location"]).path
        diagnosis_id = int(diagnosis_url.rsplit("/", 1)[1])
        with closing(sqlite3.connect(self.database_path)) as connection:
            diagnosis = connection.execute(
                """
                SELECT outcome, image_path
                FROM diagnoses
                WHERE id = ?
                """,
                (diagnosis_id,),
            ).fetchone()
            candidate = connection.execute(
                """
                SELECT d.slug, dc.match_score, dc.matched_rule_codes
                FROM diagnosis_candidates AS dc
                JOIN diseases AS d ON d.id = dc.disease_id
                WHERE dc.diagnosis_id = ?
                """,
                (diagnosis_id,),
            ).fetchone()
            selected_count = connection.execute(
                "SELECT COUNT(*) FROM diagnosis_symptoms WHERE diagnosis_id = ?",
                (diagnosis_id,),
            ).fetchone()[0]

        self.assertEqual(diagnosis[0], "matched")
        self.assertTrue(diagnosis[1])
        self.assertTrue((self.upload_path / diagnosis[1]).is_file())
        self.assertEqual(candidate[0], "early_blight")
        self.assertGreater(candidate[1], 0)
        self.assertEqual(candidate[2], "tomato_early_blight")
        self.assertEqual(selected_count, 2)

        result_response = self.client.get(diagnosis_url)
        self.assertEqual(result_response.status_code, 200)
        self.assertIn(b"possible disease matches", result_response.data.lower())
        self.assertIn(b"not a probability", result_response.data)

        image_response = self.client.get(
            f"/farmer/diagnoses/{diagnosis_id}/image"
        )
        self.assertEqual(image_response.status_code, 200)
        self.assertIn("private", image_response.headers["Cache-Control"])
        self.assertEqual(image_response.headers["X-Content-Type-Options"], "nosniff")
        image_response.close()

    def test_uploaded_image_is_not_used_to_classify_unmatched_symptoms(self) -> None:
        """Verify uploaded photos do not influence symptom-only disease inference."""
        response = self.client.post(
            "/farmer/crops/tomato",
            data={
                "symptoms": ["general_yellowing_older_leaves"],
                "crop_image": (self.create_image(), "plant.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        diagnosis_id = int(
            urlparse(response.headers["Location"]).path.rsplit("/", 1)[1]
        )
        response.close()

        with closing(sqlite3.connect(self.database_path)) as connection:
            diagnosis = connection.execute(
                "SELECT outcome, image_path FROM diagnoses WHERE id = ?",
                (diagnosis_id,),
            ).fetchone()
            candidate_count = connection.execute(
                "SELECT COUNT(*) FROM diagnosis_candidates WHERE diagnosis_id = ?",
                (diagnosis_id,),
            ).fetchone()[0]
        self.assertEqual(diagnosis[0], "no_match")
        self.assertTrue((self.upload_path / diagnosis[1]).is_file())
        self.assertEqual(candidate_count, 0)

    def test_invalid_upload_does_not_create_diagnosis(self) -> None:
        """Verify an invalid upload cannot create a diagnosis record."""
        response = self.client.post(
            "/farmer/crops/tomato",
            data={
                "symptoms": ["general_yellowing_older_leaves"],
                "crop_image": (BytesIO(b"invalid"), "plant.png", "image/png"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM diagnoses").fetchone()[0],
                0,
            )
        self.assertEqual(list(self.upload_path.iterdir()), [])

    def test_request_rejects_images_larger_than_configured_limit(self) -> None:
        """Verify requests exceeding the configured upload size are rejected."""
        response = self.client.post(
            "/farmer/crops/tomato",
            data={
                "symptoms": ["general_yellowing_older_leaves"],
                "crop_image": (
                    BytesIO(b"x" * (5 * 1024 * 1024 + 1)),
                    "plant.png",
                    "image/png",
                ),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 413)
        self.assertIn(b"5 MB", response.data)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM diagnoses").fetchone()[0],
                0,
            )
        response.request.environ["wsgi.input"].close()
        response.close()

    def test_farmer_cannot_view_another_users_diagnosis_image(self) -> None:
        """Verify a farmer cannot retrieve another farmer's stored image."""
        response = self.client.post(
            "/farmer/crops/tomato",
            data={
                "symptoms": ["general_yellowing_older_leaves"],
                "crop_image": (self.create_image(), "plant.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        diagnosis_id = int(
            urlparse(response.headers["Location"]).path.rsplit("/", 1)[1]
        )
        self.client.post("/logout")
        self.create_user("other@example.test")
        self.login("other@example.test")

        self.assertEqual(
            self.client.get(
                f"/farmer/diagnoses/{diagnosis_id}/image"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/farmer/diagnoses/{diagnosis_id}").status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
