"""File-preview tests: actual HTTP responses and temporary files, no live SQL."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from test_jobs_api import api, queries


class DocumentPreviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "data"
        self.root.mkdir()
        self.document = queries.Document(
            id="doc-1",
            relative_path="report.txt",
            filename="report",
            extension=".txt",
            content_hash="hash",
            size_bytes=5,
            is_present=True,
        )
        (self.root / "report.txt").write_text("Hello <script>not HTML</script>")
        self.root_patch = patch.object(api, "DOCUMENTS_ROOT", self.root)
        self.lookup_patch = patch.object(
            api, "get_document_query", return_value=self.document
        )
        self.root_patch.start()
        self.lookup = self.lookup_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.lookup_patch.stop)
        self.client = TestClient(api.app, raise_server_exceptions=False)

    def test_present_text_is_returned_inline_as_plain_text(self):
        response = self.client.get("/documents/doc-1/preview")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "Hello <script>not HTML</script>")
        self.assertTrue(response.headers["content-type"].startswith("text/plain"))
        self.assertIn("inline", response.headers["content-disposition"])
        self.assertIn("report.txt", response.headers["content-disposition"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.lookup.assert_called_once_with("doc-1")

    def test_pdf_bytes_are_preserved(self):
        content = b"%PDF-1.4\npreview-test"
        (self.root / "report.pdf").write_bytes(content)
        self.document.relative_path = "report.pdf"
        response = self.client.get("/documents/doc-1/preview")
        self.assertEqual(response.content, content)
        self.assertEqual(response.headers["content-type"], "application/pdf")

    def test_images_are_returned_with_allowlisted_type(self):
        (self.root / "report.png").write_bytes(b"image-bytes")
        self.document.relative_path = "report.png"
        response = self.client.get("/documents/doc-1/preview")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")

    def test_absent_document_is_not_served_even_if_file_exists(self):
        self.document.is_present = False
        response = self.client.get("/documents/doc-1/preview")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"], "This document is currently unavailable."
        )

    def test_unknown_document_is_unavailable(self):
        self.lookup.return_value = None
        self.assertEqual(self.client.get("/documents/missing/preview").status_code, 404)

    def test_missing_file_and_missing_root_are_unavailable(self):
        (self.root / "report.txt").unlink()
        self.assertEqual(self.client.get("/documents/doc-1/preview").status_code, 404)
        self.root.rmdir()
        self.assertEqual(self.client.get("/documents/doc-1/preview").status_code, 404)

    def test_traversal_absolute_and_directory_paths_are_not_served(self):
        (self.root.parent / "secret.txt").write_text("private")
        for path in ["../secret.txt", str(self.root.parent / "secret.txt"), "."]:
            with self.subTest(path=path):
                self.document.relative_path = path
                response = self.client.get("/documents/doc-1/preview")
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("private", response.text)

    def test_symlink_outside_document_root_is_not_served(self):
        secret = self.root.parent / "secret.txt"
        secret.write_text("private")
        (self.root / "link.txt").symlink_to(secret)
        self.document.relative_path = "link.txt"
        self.assertEqual(self.client.get("/documents/doc-1/preview").status_code, 404)

    def test_active_file_types_are_not_served(self):
        for extension in ["html", "svg", "js"]:
            with self.subTest(extension=extension):
                path = f"report.{extension}"
                (self.root / path).write_text("<script>alert(1)</script>")
                self.document.relative_path = path
                response = self.client.get("/documents/doc-1/preview")
                self.assertEqual(response.status_code, 415)
                self.assertNotIn("<script>", response.text)

    def test_actual_file_size_is_limited_not_sql_metadata_size(self):
        with patch.object(api, "MAX_PREVIEW_BYTES", 1):
            self.assertEqual(
                self.client.get("/documents/doc-1/preview").status_code, 413
            )

    def test_invalid_document_id_is_rejected_before_lookup(self):
        response = self.client.get(f"/documents/{'x' * 65}/preview")
        self.assertEqual(response.status_code, 422)
        self.lookup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
