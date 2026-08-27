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

    def test_start_stop_forwarder(self):
        import time as _time
        # Start
        resp = self.client.post("/api/forward/start")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])

        # Give the background thread time to update status
        _time.sleep(0.5)

        # Check status reflects start
        resp = self.client.get("/api/status")
        data = resp.get_json()
        # The thread may fail due to invalid session, but running flag should be set
        self.assertTrue(data["running"] or data["success"])

        # Stop
        resp = self.client.post("/api/forward/stop")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])

        # Back to stopped
        resp = self.client.get("/api/status")
        data = resp.get_json()
        self.assertFalse(data["running"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
