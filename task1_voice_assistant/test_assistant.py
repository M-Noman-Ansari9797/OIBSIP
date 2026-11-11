"""Unit tests for the assistant's language-understanding logic (no microphone needed)."""
import unittest

import assistant as a


class IntentTests(unittest.TestCase):
    def check(self, sentence, expected):
        intent, _ = a.classify_intent(sentence)
        self.assertEqual(intent, expected, sentence)

    def test_greeting(self):
        self.check("hello", "greeting")
        self.check("hey good morning", "greeting")

    def test_time_and_date(self):
        self.check("what time is it", "time")
        self.check("can you tell me the time please", "time")
        self.check("what is today's date", "date")

    def test_free_form_sentences(self):
        self.check("could you look up python tutorials for me", "search")
        self.check("how is the weather in lahore", "weather")
        self.check("remind me to drink water in 10 minutes", "reminder")
        self.check("i want to send an email to my friend", "email")
        self.check("who is albert einstein", "knowledge")

    def test_exit(self):
        self.check("goodbye", "exit")

    def test_unknown(self):
        self.check("purple elephants dancing", "unknown")


class EntityTests(unittest.TestCase):
    def test_duration(self):
        self.assertEqual(a.parse_duration("remind me in 5 minutes"), 300)
        self.assertEqual(a.parse_duration("in two hours"), 7200)
        self.assertEqual(a.parse_duration("after 30 seconds"), 30)
        self.assertIsNone(a.parse_duration("remind me later"))

    def test_search_query(self):
        self.assertEqual(a.extract_search_query("search for python tutorials"), "python tutorials")
        self.assertEqual(a.extract_search_query("google machine learning"), "machine learning")

    def test_city(self):
        self.assertEqual(a.extract_city("weather in lahore today"), "Lahore")

    def test_topic(self):
        self.assertEqual(a.extract_topic("who is albert einstein"), "albert einstein")

    def test_format_duration(self):
        self.assertEqual(a.format_duration(90), "1 minute and 30 seconds")


if __name__ == "__main__":
    unittest.main()
