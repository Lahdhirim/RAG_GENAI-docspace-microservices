"""Exercise real SQL mapping and FastAPI routes without external services.

Run: python -m unittest discover -s src/services/doc_manager_service/tests -v
"""

import importlib
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

SERVICE = Path(__file__).resolve().parents[1]
SHARED = SERVICE.parents[1] / "shared"
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(SERVICE))
connection_module = types.ModuleType("database.connection")
connection_module.connection = MagicMock()
connection_module.cursor = MagicMock()
with patch.dict(sys.modules, {"database.connection": connection_module}):
    queries = importlib.import_module("database.queries")
    api = importlib.import_module("app")


class JobsApiTests(unittest.TestCase):
    def setUp(self):
        self.cursor = connection_module.cursor
        self.connection = connection_module.connection
        self.cursor.reset_mock(side_effect=True, return_value=True)
        self.connection.reset_mock()
        self.client = TestClient(api.app, raise_server_exceptions=False)
        self.now = datetime(2026, 11, 9, 10, 30)
        self.row = (
            "job-1",
            "doc-1",
            self.now,
            "FAILED",
            self.now,
            None,
            0.0,
            None,
            "Parser unavailable",
            "Report.pdf",
            "reports/Report.pdf",
        )

    def test_lists_sql_jobs_with_metadata_and_serializes_dates_and_nulls(self):
        self.cursor.fetchall.return_value = [self.row]
        response = self.client.get("/jobs")
        self.assertEqual(response.status_code, 200)
        job = response.json()["jobs"][0]
        self.assertEqual(job["filename"], "Report.pdf")
        self.assertEqual(job["status"], "FAILED")
        self.assertEqual(job["submitted_at"], "2026-11-09T10:30:00")
        self.assertEqual(job["waiting_duration"], 0)
        self.assertIsNone(job["execution_duration"])
        self.assertIsNone(job["finished_at"])
        self.assertEqual(job["error"], "Parser unavailable")
        sql, parameters = self.cursor.execute.call_args.args
        self.assertIn("LEFT JOIN documents", sql)
        self.assertIn("ORDER BY j.submitted_at DESC, j.job_id DESC", sql)
        self.assertEqual(parameters, ())
        self.connection.commit.assert_not_called()

    def test_document_filter_is_parameterized(self):
        document_id = "' OR 1=1 --"
        self.cursor.fetchall.return_value = []
        response = self.client.get("/jobs", params={"document_id": document_id})
        self.assertEqual(response.json(), {"jobs": []})
        sql, parameters = self.cursor.execute.call_args.args
        self.assertIn("WHERE j.document_id = %s", sql)
        self.assertNotIn(document_id, sql)
        self.assertEqual(parameters, (document_id,))

    def test_all_recorded_statuses_are_supported(self):
        statuses = [
            "QUEUED",
            "NOT_FOUND",
            "RUNNING",
            "COMPLETED",
            "FAILED",
            "NOT_STARTED",
            "UNKNOWN",
        ]
        self.cursor.fetchall.return_value = [
            self.row[:3] + (status,) + self.row[4:] for status in statuses
        ]
        self.assertEqual(
            [j["status"] for j in self.client.get("/jobs").json()["jobs"]], statuses
        )

    def test_missing_joined_metadata_is_preserved(self):
        self.cursor.fetchall.return_value = [self.row[:-2] + (None, None)]
        response = self.client.get("/jobs")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["jobs"][0]["filename"])

    def test_invalid_document_filters_are_rejected_before_sql(self):
        for value in ["", "x" * 65]:
            with self.subTest(value=value):
                self.assertEqual(
                    self.client.get("/jobs", params={"document_id": value}).status_code,
                    422,
                )
        self.cursor.execute.assert_not_called()

    def test_database_failure_is_not_reported_as_an_empty_library(self):
        self.cursor.execute.side_effect = RuntimeError("private database details")
        response = self.client.get("/jobs")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private database details", response.text)
        self.connection.rollback.assert_called_once()

    def test_no_job_mutations_are_exposed(self):
        self.assertEqual(self.client.post("/jobs", json={}).status_code, 405)
        self.cursor.execute.assert_not_called()

    def test_documents_keep_submission_status_from_sql(self):
        self.cursor.fetchall.return_value = [
            (
                "doc-1",
                "reports/Report.pdf",
                "Report.pdf",
                ".pdf",
                "hash",
                2048,
                None,
                None,
                None,
                1,
                "SUBMITTED",
                0,
                self.now,
                self.now,
            )
        ]
        response = self.client.get("/documents")
        self.assertEqual(response.status_code, 200)
        document = response.json()["documents"][0]
        self.assertEqual(document["submission_status"], "SUBMITTED")
        self.assertIs(document["is_parsed"], False)
        self.assertIs(document["is_present"], True)


if __name__ == "__main__":
    unittest.main()
