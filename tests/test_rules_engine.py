"""
Unit tests for the RulesEngine.
Tests text replacement, regex stripping, footer appending, and blacklist checking
using an in-memory fake database (no real MongoDB required).
"""
import unittest

import tests.conftest  # noqa: F401

from src.rules.engine import RulesEngine


class FakeCollection:
    """Minimal stand-in for a MongoDB collection."""

    def __init__(self):
        self._docs = []

    def find(self, query=None):
        # Filter docs matching all key/value pairs in query (simple equality)
        if not query:
            return list(self._docs)
        results = []
        for doc in self._docs:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                results.append(doc)
        return results

    def find_one(self, query=None):
        if not query:
            return self._docs[0] if self._docs else None
        for doc in self._docs:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                return doc
        return None

    def insert_one(self, doc):
        self._docs.append(doc)

    def insert_many(self, docs):
        for d in docs:
            self._docs.append(d)

    def delete_one(self, query):
        for i, doc in enumerate(self._docs):
            match = all(doc.get(k) == v for k, v in query.items())
            if match:
                self._docs.pop(i)
                break

    def count_documents(self, query=None):
        if not query:
            return len(self._docs)
        return sum(
            1
            for doc in self._docs
            if all(doc.get(k) == v for k, v in query.items())
        )


class FakeDB:
    """Minimal stand-in for the MongoDB wrapper used by RulesEngine."""

    def __init__(self):
        self.rules = FakeCollection()
        self.blacklist = FakeCollection()
        self.processed_posts = FakeCollection()

    def create_index(self, *args, **kwargs):
        pass


class RulesEngineReplaceTest(unittest.TestCase):
    """Test text replacement (type='replace')."""

    def setUp(self):
        self.db = FakeDB()
        self.db.rules.insert_many([
            {
                "name": "Replace spam word",
                "type": "replace",
                "pattern": "spam",
                "replacement": "good food",
                "priority": 1,
                "active": True,
            }
        ])
        self.engine = RulesEngine(self.db)

    def test_simple_replacement(self):
        text = "I love spam"
        result = self.engine.apply_rules(text)
        self.assertEqual(result, "I love good food")

    def test_multiple_replacements(self):
        text = "spam spam spam"
        result = self.engine.apply_rules(text)
        self.assertEqual(result, "good food good food good food")

    def test_no_match_returns_original(self):
        text = "I love eggs"
        result = self.engine.apply_rules(text)
        self.assertEqual(result, "I love eggs")

    def test_empty_text(self):
        result = self.engine.apply_rules("")
        self.assertEqual(result, "")


class RulesEngineRegexTest(unittest.TestCase):
    """Test regex replacement (type='regex')."""

    def setUp(self):
        self.db = FakeDB()
        self.db.rules.insert_many([
            {
                "name": "Strip @usernames",
                "type": "regex",
                "pattern": r"@\w+",
                "replacement": "[username]",
                "priority": 1,
                "active": True,
            }
        ])
        self.engine = RulesEngine(self.db)

    def test_regex_replaces_usernames(self):
        text = "Hello @alice and @bob"
        result = self.engine.apply_rules(text)
        self.assertEqual(result, "Hello [username] and [username]")

    def test_regex_replacement_empty(self):
        """Regex with empty replacement acts like a strip."""
        self.db.rules.insert_many([
            {
                "name": "Remove hashtags",
                "type": "regex",
                "pattern": r"#\w+",
                "replacement": "",
                "priority": 0,
                "active": True,
            }
        ])
        text = "Check #tag1 and #tag2 now"
        result = self.engine.apply_rules(text)
        self.assertNotIn("#tag1", result)
        self.assertNotIn("#tag2", result)

    def test_invalid_regex_does_not_crash(self):
        self.db.rules.insert_many([
            {
                "name": "Bad regex",
                "type": "regex",
                "pattern": r"[unclosed",
                "replacement": "x",
                "priority": 0,
                "active": True,
            }
        ])
        text = "some text"
        result = self.engine.apply_rules(text)
        # Should return original text on regex error, not crash
        self.assertEqual(result, text)

    def test_priority_order(self):
        """Higher priority (lower number) rules apply first."""
        # Two rules: lowercase 'a' -> 'AA' (priority 1), then 'AA' -> 'BB' (priority 2)
        # If priority 1 runs first: a -> AA -> BB
        self.db.rules.insert_many([
            {
                "name": "a to AA",
                "type": "regex",
                "pattern": r"a",
                "replacement": "AA",
                "priority": 1,
                "active": True,
            },
            {
                "name": "AA to BB",
                "type": "regex",
                "pattern": r"AA",
                "replacement": "BB",
                "priority": 2,
                "active": True,
            },
        ])
        text = "a"
        result = self.engine.apply_rules(text)
        self.assertEqual(result, "BB")


class RulesEngineStripTest(unittest.TestCase):
    """Test strip rules (type='strip')."""

    def setUp(self):
        self.db = FakeDB()
        self.db.rules.insert_many([
            {
                "name": "Strip URLs",
                "type": "strip",
                "pattern": r"https?://\S+",
                "priority": 1,
                "active": True,
            }
        ])
        self.engine = RulesEngine(self.db)

    def test_strip_removes_matches(self):
        text = "Visit https://example.com today"
        result = self.engine.apply_rules(text)
        self.assertNotIn("https://example.com", result)

    def test_strip_preserves_surrounding_text(self):
        text = "Hello https://evil.com world"
        result = self.engine.apply_rules(text)
        self.assertIn("Hello", result)
        self.assertIn("world", result)
        self.assertNotIn("https://evil.com", result)


class RulesEngineFooterTest(unittest.TestCase):
    """Test footer rules (type='footer')."""

    def setUp(self):
        self.db = FakeDB()
        self.db.rules.insert_many([
            {
                "name": "Branding Footer",
                "type": "footer",
                "replacement": "Forwarded by Telegram Forwarder Pro",
                "priority": 99,
                "active": True,
            }
        ])
        self.engine = RulesEngine(self.db)

    def test_footer_appended(self):
        text = "Hello world"
        result = self.engine.apply_rules(text)
        self.assertTrue(result.endswith("Forwarded by Telegram Forwarder Pro"))
        self.assertIn("\n\n", result)

    def test_footer_with_original_content(self):
        text = "Original message"
        result = self.engine.apply_rules(text)
        self.assertEqual(
            result, "Original message\n\nForwarded by Telegram Forwarder Pro"
        )

    def test_empty_footer_rule(self):
        db = FakeDB()
        db.rules.insert_many([
            {
                "name": "Empty footer",
                "type": "footer",
                "replacement": "",
                "priority": 5,
                "active": True,
            }
        ])
        engine = RulesEngine(db)
        text = "Hello"
        result = engine.apply_rules(text)
        self.assertEqual(result, "Hello")


class RulesEngineBlacklistTest(unittest.TestCase):
    """Test blacklist checking."""

    def setUp(self):
        self.db = FakeDB()
        self.engine = RulesEngine(self.db)

    def test_not_blacklisted_by_default(self):
        self.assertFalse(self.engine.is_blacklisted(12345))

    def test_blacklisted_channel(self):
        self.db.blacklist.insert_one({"channel_id": 12345, "reason": "spam"})
        self.assertTrue(self.engine.is_blacklisted(12345))

    def test_not_blacklisted_when_channel_missing(self):
        self.db.blacklist.insert_one({"channel_id": 999, "reason": "spam"})
        self.assertFalse(self.engine.is_blacklisted(12345))

    def test_blacklist_with_no_db(self):
        engine = RulesEngine(db=None)
        self.assertFalse(engine.is_blacklisted(12345))


class RulesEngineInactiveRuleTest(unittest.TestCase):
    """Inactive rules should be skipped."""

    def test_inactive_rule_not_applied(self):
        db = FakeDB()
        db.rules.insert_many([
            {
                "name": "Inactive replace",
                "type": "replace",
                "pattern": "spam",
                "replacement": "good",
                "priority": 1,
                "active": False,
            }
        ])
        engine = RulesEngine(db)
        result = engine.apply_rules("I love spam")
        self.assertEqual(result, "I love spam")


class RulesEngineNoDbTest(unittest.TestCase):
    """RulesEngine works with db=None (no rules applied)."""

    def test_no_db_returns_text_unchanged(self):
        engine = RulesEngine(db=None)
        result = engine.apply_rules("Hello world")
        self.assertEqual(result, "Hello world")

    def test_no_db_blacklist_returns_false(self):
        engine = RulesEngine(db=None)
        self.assertFalse(engine.is_blacklisted(42))

    def test_no_db_load_rules_empty(self):
        engine = RulesEngine(db=None)
        self.assertEqual(engine.load_rules(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
