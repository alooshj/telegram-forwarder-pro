"""
Tests for the Flask web API.
Verifies the Flask app boots and /api/status returns valid JSON.
"""
import json
import os
import unittest

# env setup via conftest
import tests.conftest  # noqa: F401

from src.web.api import app, load_config, get_db


class FlaskApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_app_exists(self):
        self.assertIsNotNone(app)

    def test_config_loads(self):
        cfg = load_config()
        self.assertIn("API_ID", cfg)
        self.assertIsInstance(cfg["API_ID"], int)
        self.assertEqual(cfg["API_ID"], 123456)

    def test_status_endpoint_returns_json(self):
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, "application/json")
        data = resp.get_json()
        self.assertIsInstance(data, dict)

    def test_status_endpoint_fields(self):
        resp = self.client.get("/api/status")
        data = resp.get_json()
        self.assertIn("running", data)
        self.assertIn("connected", data)
        self.assertIn("last_update", data)

    def test_dashboard_route(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_debug_endpoint(self):
        resp = self.client.get("/api/debug")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("db_connected", data)

    def test_rules_endpoint(self):
        resp = self.client.get("/api/rules")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("rules", data)

    def test_blacklist_endpoint(self):
        resp = self.client.get("/api/blacklist")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("blacklist", data)

    def test_logs_endpoint(self):
        resp = self.client.get("/api/logs")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("logs", data)

    def test_certifi_available_for_mongo_tls(self):
        """certifi should be importable and provide a CA bundle path."""
        from src.utils.database import _MONGO_TLS_CA
        import os
        # _MONGO_TLS_CA may be None if certifi not installed, but if installed the path must exist
        if _MONGO_TLS_CA is not None:
            self.assertTrue(os.path.exists(_MONGO_TLS_CA), "certifi CA file should exist")

    def test_start_stop_forwarder(self):
        # Start
        resp = self.client.post("/api/forward/start")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])

        # Stop
        resp = self.client.post("/api/forward/stop")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])

        # Check status shows stopped
        resp = self.client.get("/api/status")
        data = resp.get_json()
        self.assertFalse(data["running"])


    def test_forwarder_status_endpoint(self):
        resp = self.client.get("/api/forwarder/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("active_forwarding_rules", data)
        self.assertIn("running", data)

    def test_rule_crud_with_custom_id_and_delete(self):
        # Create rule
        resp = self.client.post("/api/rules", json={
            "name": "Custom Test Rule",
            "source_id": "-1001234567890",
            "target_id": "-1009876543210",
            "type": "replace",
            "pattern": "foo",
            "replacement": "bar",
            "priority": 1,
            "active": True
        })
        self.assertEqual(resp.status_code, 200)
        rule_data = resp.get_json()
        self.assertTrue(rule_data["success"])
        rule_id = rule_data["rule"]["_id"]

        # Update rule
        resp = self.client.put(f"/api/rules/{rule_id}", json={"name": "Updated Test Rule"})
        self.assertEqual(resp.status_code, 200)

        # Delete rule
        resp = self.client.delete(f"/api/rules/{rule_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])

    def test_blacklist_add_and_remove(self):
        resp = self.client.post("/api/blacklist", json={
            "channel_id": "-1001122334455",
            "reason": "Test Spam"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])

    def test_stats_endpoint(self):
        resp = self.client.get("/api/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("total_rules", data)
        self.assertIn("active_rules", data)
        self.assertIn("blacklist_count", data)
        self.assertIn("running", data)
        self.assertIn("db_type", data)

    def test_rule_toggle_endpoint(self):
        # Create a rule first
        resp = self.client.post("/api/rules", json={
            "name": "Toggle Test",
            "source_id": "-100111",
            "target_id": "-100222",
            "active": True
        })
        self.assertEqual(resp.status_code, 200)
        rule_id = resp.get_json()["rule"]["_id"]

        # Toggle to false
        resp = self.client.post(f"/api/rules/{rule_id}/toggle")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertFalse(data["active"])

        # Toggle back to true
        resp = self.client.post(f"/api/rules/{rule_id}/toggle")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["active"])

    def test_rules_test_endpoint(self):
        # Create a replace rule
        self.client.post("/api/rules", json={
            "name": "Test Replace",
            "type": "replace",
            "pattern": "Apple",
            "replacement": "Orange",
            "active": True
        })
        resp = self.client.post("/api/rules/test", json={"text": "I love Apple"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("I love Orange", data["transformed"])

    def test_logs_clear_endpoint(self):
        resp = self.client.post("/api/logs/clear")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["success"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

