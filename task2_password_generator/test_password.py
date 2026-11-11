"""Unit tests for the password generator logic."""
import unittest

import password_cli as cli
import password_core as core


class GenerationTests(unittest.TestCase):
    def test_length_is_exact(self):
        for length in (8, 12, 32, 128):
            pw = core.generate_password(length, ["uppercase", "lowercase"])
            self.assertEqual(len(pw), length)

    def test_every_selected_type_present(self):
        # Repeat many times: the guarantee must hold on every single run.
        types = ["uppercase", "lowercase", "numbers", "symbols"]
        for _ in range(500):
            pw = core.generate_password(8, types)
            self.assertTrue(any(c.isupper() for c in pw))
            self.assertTrue(any(c.islower() for c in pw))
            self.assertTrue(any(c.isdigit() for c in pw))
            self.assertTrue(any(c in core.CHARSETS["symbols"] for c in pw))

    def test_only_selected_types_used(self):
        for _ in range(200):
            pw = core.generate_password(20, ["lowercase", "numbers"])
            self.assertTrue(all(c.islower() or c.isdigit() for c in pw))

    def test_ambiguous_excluded(self):
        for _ in range(300):
            pw = core.generate_password(30, ["uppercase", "lowercase", "numbers", "symbols"],
                                        exclude_ambiguous=True)
            self.assertFalse(set(pw) & core.AMBIGUOUS)

    def test_passwords_differ(self):
        samples = {core.generate_password(16, ["uppercase", "numbers"]) for _ in range(100)}
        self.assertEqual(len(samples), 100)


class ValidationTests(unittest.TestCase):
    def test_short_length_rejected(self):
        with self.assertRaises(ValueError):
            core.generate_password(7, ["uppercase", "lowercase"])

    def test_too_long_rejected(self):
        with self.assertRaises(ValueError):
            core.generate_password(129, ["uppercase", "lowercase"])

    def test_fewer_than_two_types_rejected(self):
        with self.assertRaises(ValueError):
            core.generate_password(12, ["uppercase"])
        with self.assertRaises(ValueError):
            core.generate_password(12, [])

    def test_unknown_type_rejected(self):
        with self.assertRaises(ValueError):
            core.generate_password(12, ["uppercase", "emoji"])


class StrengthTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(core.strength("abc12345")[0], "Weak")
        self.assertEqual(core.strength("Passw0rd!Xy")[0], "Medium")
        self.assertEqual(core.strength("Tr7#kQ9!vL2@pZ8$wN")[0], "Strong")

    def test_repetition_penalised(self):
        self.assertEqual(core.strength("aaaaaaaaaaaaaaaaaaaa")[0], "Weak")

    def test_score_bounds(self):
        for pw in ("a", "A1!" * 50):
            score = core.strength(pw)[1]
            self.assertTrue(0 <= score <= 100)


class CliTests(unittest.TestCase):
    def test_cli_generation_rules(self):
        for _ in range(300):
            pw = cli.generate(10, ["1", "3"])
            self.assertEqual(len(pw), 10)
            self.assertTrue(any(c.isupper() for c in pw))
            self.assertTrue(any(c.isdigit() for c in pw))


if __name__ == "__main__":
    unittest.main()
