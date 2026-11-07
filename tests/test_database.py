import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.database.seed import initialize_database


class DatabaseInitializationTests(unittest.TestCase):
    def test_initialization_creates_seeded_knowledge_base(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "test.sqlite3"
            initialize_database(database_path)

            with closing(sqlite3.connect(database_path)) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM crops").fetchone()[0],
                    2,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM diseases").fetchone()[0],
                    8,
                )
                self.assertGreater(
                    connection.execute("SELECT COUNT(*) FROM symptoms").fetchone()[0],
                    0,
                )
                self.assertGreater(
                    connection.execute("SELECT COUNT(*) FROM rule_conditions").fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM diseases d
                        WHERE NOT EXISTS (
                            SELECT 1 FROM disease_sources ds
                            WHERE ds.disease_id = d.id
                        )
                        """
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute("PRAGMA foreign_key_check").fetchall(),
                    [],
                )

    def test_reinitialization_does_not_duplicate_seed_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "test.sqlite3"
            initialize_database(database_path)
            initialize_database(database_path)

            with closing(sqlite3.connect(database_path)) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM diseases").fetchone()[0],
                    8,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM rules").fetchone()[0],
                    10,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM treatments").fetchone()[0],
                    16,
                )


if __name__ == "__main__":
    unittest.main()
