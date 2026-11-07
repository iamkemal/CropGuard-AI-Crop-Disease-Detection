import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.database.seed import initialize_database
from app.services.inference_engine import infer_disease


class InferenceEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.database_path = Path(temporary_directory.name) / "test.sqlite3"
        initialize_database(self.database_path)
        self.connection = sqlite3.connect(self.database_path)
        self.addCleanup(self.connection.close)

    def test_matches_disease_and_explains_rule_evidence(self) -> None:
        result = infer_disease(
            self.connection,
            "maize",
            (
                "long_cigar_shaped_lesions",
                "maize_lower_leaf_lesions",
                "gray_tan_leaf_lesions",
            ),
        )

        self.assertEqual(result.outcome, "matched")
        self.assertEqual(result.candidates[0].slug, "northern_leaf_blight")
        self.assertEqual(result.candidates[0].match_score, 1.0)
        self.assertEqual(
            result.candidates[0].confidence_level,
            "high",
        )
        self.assertEqual(
            result.candidates[0].matched_rules[0].code,
            "maize_northern_leaf_blight",
        )
        self.assertIn("possible diagnosis", result.explanation)

    def test_returns_multiple_similarly_scored_disease_candidates(self) -> None:
        result = infer_disease(
            self.connection,
            "tomato",
            (
                "dark_lower_leaf_spots",
                "concentric_rings_in_spots",
                "yellowing_around_leaf_spots",
                "water_soaked_irregular_lesions",
                "white_growth_leaf_underside",
                "firm_brown_fruit_lesions",
            ),
        )

        self.assertEqual(result.outcome, "matched")
        self.assertEqual(
            {candidate.slug for candidate in result.candidates},
            {"early_blight", "late_blight"},
        )
        self.assertIn("similarly strong", result.explanation)

    def test_reports_insufficient_evidence_for_partial_rule(self) -> None:
        result = infer_disease(
            self.connection,
            "maize",
            ("long_cigar_shaped_lesions",),
        )

        self.assertEqual(result.outcome, "insufficient_evidence")
        self.assertEqual(result.candidates, ())
        self.assertTrue(result.rule_evidence)
        self.assertEqual(
            result.rule_evidence[0].missing_required_symptoms,
            (),
        )
        self.assertIn("at least 2 matched symptoms", result.explanation)

    def test_reports_no_match_when_symptoms_have_no_rule_conditions(self) -> None:
        result = infer_disease(
            self.connection,
            "tomato",
            ("general_yellowing_older_leaves",),
        )

        self.assertEqual(result.outcome, "no_match")
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.rule_evidence, ())

    def test_empty_symptom_selection_is_insufficient_evidence(self) -> None:
        result = infer_disease(self.connection, "tomato", ())

        self.assertEqual(result.outcome, "insufficient_evidence")
        self.assertEqual(result.confidence_level, "none")

    def test_rejects_symptoms_from_another_crop(self) -> None:
        with self.assertRaisesRegex(ValueError, "do not belong to tomato"):
            infer_disease(
                self.connection,
                "tomato",
                ("long_cigar_shaped_lesions",),
            )

    def test_rejects_unknown_crop(self) -> None:
        with self.assertRaises(LookupError):
            infer_disease(self.connection, "potato", ())


if __name__ == "__main__":
    unittest.main()
