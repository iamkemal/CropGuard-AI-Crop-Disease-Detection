"""Isolated Flask application fixtures shared by the integration test cases."""

import tempfile
import unittest
from pathlib import Path

from app import create_app


class FlaskTestCase(unittest.TestCase):
    """Give each test its own database, upload directory, and browser client."""

    def setUp(self) -> None:
        """Create temporary application storage and register automatic cleanup."""
        # unittest closes this context after the test, rather than at the end of setUp.
        temporary_directory = self.enterContext(
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        self.temporary_path = Path(temporary_directory)
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
