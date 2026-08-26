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
        # Default state: not running, not connected
        self.assertFalse(data["running"])
        self.assertFalse(data["connected"])

    def test_status_endpoint_start_stop(self):
        # Start
        resp = self.client.post("/api/forward/start")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["status"]["running"])
        self.assertTrue(data["status"]["connected"])

        # Check status reflects start
        resp = self.client.get("/api/status")
        data = resp.get_json()
        self.assertTrue(data["running"])

        # Stop
        resp = self.client.post("/api/forward/stop")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertFalse(data["status"]["running"])
        self.assertFalse(data["status"]["connected"])

        # Back to stopped
        resp = self.client.get("/api/status")
        data = resp.get_json()
        self.assertFalse(data["running"])

    def test_dashboard_route(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_404_handler(self):
        resp = self.client.get("/api/nonexistent")
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertIn("error", data)

    def test_db_ref_is_none_by_default(self):
        self.assertIsNone(get_db())


if __name__ == "__main__":
    unittest.main(verbosity=2)
