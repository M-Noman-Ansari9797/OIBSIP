"""Unit tests for BMI logic and the SQLite layer."""
import os
import tempfile
import unittest
from datetime import datetime

import bmi_core as core


class CalculationTests(unittest.TestCase):
    def test_formula(self):
        self.assertAlmostEqual(core.calculate_bmi(70, 1.75), 22.857, places=3)

    def test_boundaries(self):
        self.assertEqual(core.classify_bmi(18.49), "Underweight")
        self.assertEqual(core.classify_bmi(18.5), "Normal")
        self.assertEqual(core.classify_bmi(24.9), "Normal")
        self.assertEqual(core.classify_bmi(25.0), "Overweight")
        self.assertEqual(core.classify_bmi(29.9), "Overweight")
        self.assertEqual(core.classify_bmi(30.0), "Obese")

    def test_rejects_non_positive(self):
        with self.assertRaises(ValueError):
            core.calculate_bmi(-5, 1.7)
        with self.assertRaises(ValueError):
            core.calculate_bmi(70, 0)


class ValidationTests(unittest.TestCase):
    def test_non_numeric(self):
        with self.assertRaises(ValueError):
            core.parse_positive_float("abc", "Weight")

    def test_empty_and_negative(self):
        for bad in ("", "   ", "-3", "0"):
            with self.assertRaises(ValueError):
                core.parse_positive_float(bad, "Weight")

    def test_nan_inf(self):
        for bad in ("nan", "inf"):
            with self.assertRaises(ValueError):
                core.parse_positive_float(bad, "Height")

    def test_valid(self):
        self.assertEqual(core.parse_positive_float(" 1.75 ", "Height"), 1.75)

    def test_range_catches_centimetres(self):
        with self.assertRaises(ValueError):
            core.validate_ranges(70, 175)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = core.BMIDatabase(self.path)

    def tearDown(self):
        os.remove(self.path)

    def test_multi_user_and_history_order(self):
        self.db.add_record("Ali", 70, 1.75, 22.86, "Normal", datetime(2026, 1, 1))
        self.db.add_record("Ali", 75, 1.75, 24.49, "Normal", datetime(2026, 2, 1))
        self.db.add_record("Sara", 55, 1.62, 20.96, "Normal", datetime(2026, 1, 5))
        self.assertEqual(self.db.users(), ["Ali", "Sara"])
        history = self.db.history("Ali")
        self.assertEqual(len(history), 2)
        self.assertLess(history[0][0], history[1][0])
        self.assertEqual(len(self.db.history("Sara")), 1)

    def test_delete_user(self):
        self.db.add_record("Ali", 70, 1.75, 22.86, "Normal")
        self.assertEqual(self.db.delete_user("Ali"), 1)
        self.assertEqual(self.db.history("Ali"), [])

    def test_sql_injection_is_harmless(self):
        self.db.add_record("x'; DROP TABLE records;--", 70, 1.75, 22.86, "Normal")
        self.assertEqual(len(self.db.users()), 1)

    def test_database_failure_is_reported(self):
        bad = core.BMIDatabase.__new__(core.BMIDatabase)
        bad.path = "/nonexistent_dir/forbidden.db"
        with self.assertRaises(core.DatabaseError):
            bad.add_record("a", 1, 1, 1, "Normal")


if __name__ == "__main__":
    unittest.main()
