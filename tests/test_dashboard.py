"""Protect ownership and ordering in the farmer dashboard's recent records."""

import sqlite3
from contextlib import closing

from flask import template_rendered

from tests.support import FlaskTestCase


class FarmerDashboardTests(FlaskTestCase):
    """Keep recent assessments private, limited, and deterministic."""

    def test_recent_records_belong_to_current_farmer(self) -> None:
        """Exclude a newer foreign record and order tied timestamps by ID."""
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.executemany(
                    """INSERT INTO users (id, username, email, password_hash)
                       VALUES (?, ?, ?, ?)""",
                    [
                        (1, "Farmer One", "one@example.test", "unused-test-hash"),
                        (2, "Farmer Two", "two@example.test", "unused-test-hash"),
                    ],
                )
                crop_id = connection.execute("SELECT id FROM crops LIMIT 1").fetchone()[0]
                connection.executemany(
                    """INSERT INTO diagnoses
                       (id, user_id, crop_id, outcome, confidence_level,
                        explanation, created_at)
                       VALUES (?, ?, ?, 'no_match', 'none', 'Test record', ?)""",
                    [
                        (record_id, 1, crop_id, "2026-01-01 12:00:00")
                        for record_id in range(1, 6)
                    ] + [(6, 2, crop_id, "2026-01-02 12:00:00")],
                )

        contexts = []

        def capture_context(_sender, template, context, **_extra):
            if template.name == "farmer/dashboard.html":
                contexts.append(context)

        with self.client.session_transaction() as state:
            state["user_id"] = 1
        with template_rendered.connected_to(capture_context, self.app):
            response = self.client.get("/farmer/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(contexts[0]["diagnosis_count"], 5)
        self.assertEqual(contexts[0]["latest_diagnosis"]["id"], 5)
        self.assertEqual(
            [row["id"] for row in contexts[0]["recent_diagnoses"]], [5, 4, 3]
        )
