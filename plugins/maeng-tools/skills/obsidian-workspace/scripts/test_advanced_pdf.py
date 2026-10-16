import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
import advanced_pdf


class AdvancedPdfTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.home = self.root / "models"
        self.home.mkdir()
        (self.home / "weights").write_bytes(b"fixture weights")
        self.config = self.root / "runtime.json"
        self.value = {"engine": "mineru", "version": advanced_pdf.VERSION, "python": str(Path(os.sys.executable).absolute()),
                      "model_home": str(self.home), "models": [{"path": "weights", "sha256": advanced_pdf.digest(self.home / "weights")}]}
        self.config.write_text(json.dumps(self.value))
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.add_blank_page(width=200, height=200)
        stream = io.BytesIO()
        writer.write(stream)
        self.raw = stream.getvalue()

    def run_engine(self, argv, **kwargs):
        self.assertEqual(argv[1], "-I")
        self.assertEqual(kwargs["env"]["MINERU_MODEL_SOURCE"], "local")
        self.assertEqual(kwargs["env"]["HF_HUB_OFFLINE"], "1")
        self.assertNotIn("MINERU_MODEL_VLM_SERVER_URL", kwargs["env"])
        self.assertEqual(Path(kwargs["env"]["MINERU_CONFIG"]).read_text(), "{}\n")
        Path(argv[-2]).write_text(json.dumps({"version": advanced_pdf.VERSION,
            "pages": [{"page": 1, "text": "$$x^2$$", "image_count": 1}]}))
        return SimpleNamespace(returncode=0)

    def test_selected_page_mapping_and_local_only_environment(self):
        with patch.dict(os.environ, {"MINERU_MODEL_VLM_SERVER_URL": "https://example.invalid"}), patch.object(advanced_pdf.subprocess, "run", side_effect=self.run_engine):
            result = advanced_pdf.extract(self.raw, [2], self.config)
        self.assertEqual(result["sections"][0]["position"], "page 2")
        self.assertEqual(result["sections"][0]["omitted_images"], 1)
        self.assertEqual(result["engine"]["pages"], [2])

    def test_rejects_invalid_pages_and_tampered_models_before_execution(self):
        with patch.object(advanced_pdf.subprocess, "run") as run:
            for pages in [[], [0], [3], [1, 1], [True]]:
                with self.assertRaises(ValueError):
                    advanced_pdf.extract(self.raw, pages, self.config)
            (self.home / "weights").write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                advanced_pdf.extract(self.raw, [1], self.config)
            run.assert_not_called()

    def test_rejects_wrong_version_coverage_and_subprocess_failure(self):
        for result_value in [{"version": "other", "pages": []}, {"version": advanced_pdf.VERSION, "pages": []}]:
            def bad(argv, **kwargs):
                Path(argv[-2]).write_text(json.dumps(result_value))
                return SimpleNamespace(returncode=0)
            with patch.object(advanced_pdf.subprocess, "run", side_effect=bad), self.assertRaises(ValueError):
                advanced_pdf.extract(self.raw, [1], self.config)
        with patch.object(advanced_pdf.subprocess, "run", return_value=SimpleNamespace(returncode=1, stderr="engine failed")), self.assertRaisesRegex(ValueError, "engine failed"):
            advanced_pdf.extract(self.raw, [1], self.config)

    def test_unwraps_only_generated_algorithm_container_preserving_math_and_table(self):
        text = '<div class="docvortex-algorithm" style="white-space: pre-wrap;">\n1 $v^T w=0$\n</div>\n<table><tr><td rowspan="2">9/1</td></tr></table>'
        actual, images = advanced_pdf.obsidian_text(text)
        self.assertIn("$v^T w=0$", actual)
        self.assertNotIn("<div", actual)
        self.assertIn('rowspan="2"', actual)
        self.assertEqual(images, 0)

    def test_inline_image_payloads_are_omitted_and_counted(self):
        actual, images = advanced_pdf.obsidian_text('Before $x^2$ ![](data:image/jpeg;base64,SECRETBASE64) after')
        self.assertEqual(images, 1)
        self.assertIn("[Image retained in original PDF; not interpreted]", actual)
        self.assertIn("$x^2$", actual)
        self.assertNotIn("data:image", actual)
        self.assertNotIn("SECRETBASE64", actual)
        with self.assertRaisesRegex(ValueError, "Unexpected inline image"):
            advanced_pdf.obsidian_text('<img src="data:image/png;base64,UNEXPECTED">')


if __name__ == "__main__":
    unittest.main()
