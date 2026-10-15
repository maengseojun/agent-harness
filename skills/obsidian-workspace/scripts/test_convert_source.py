import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import json

from docx import Document
from pptx import Presentation
from pptx.util import Inches
from pypdf import PdfWriter
from reportlab.pdfgen import canvas
from types import SimpleNamespace

import convert_source as conversion


class ConversionTests(unittest.TestCase):
    def test_cli_failures_return_json_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ["missing.pdf", "bad.pdf"]:
                path = Path(folder) / name
                if name == "bad.pdf":
                    path.write_bytes(b"not a PDF")
                output = io.StringIO()
                argv = ["convert", "--source-root", folder, "--path", name,
                        "--sha256", hashlib.sha256(b"not a PDF").hexdigest(),
                        "--origin", "synthetic:bad", "--fetched-at", "2026-10-15T00:00:00Z"]
                with patch("sys.argv", argv), redirect_stdout(output):
                    self.assertEqual(conversion.main(), 1)
                receipt = json.loads(output.getvalue())
                self.assertFalse(receipt["ok"])
                self.assertEqual(receipt["note_writes"], 0)

    def test_word_preserves_block_order_and_table(self):
        doc = Document()
        doc.add_heading("Before", 1)
        doc.add_table(rows=1, cols=1).cell(0, 0).text = "A|B"
        doc.add_paragraph("After")
        stream = io.BytesIO()
        doc.save(stream)
        result = conversion.extract(stream.getvalue(), ".docx", False)
        body = result["sections"][0]["text"]
        self.assertLess(body.index("Before"), body.index("A\\|B"))
        self.assertLess(body.index("A\\|B"), body.index("After"))
        self.assertIn("not paginated", result["sections"][0]["position"])

    def test_ppt_retains_slide_boundaries(self):
        deck = Presentation()
        for text in ["first", "second"]:
            slide = deck.slides.add_slide(deck.slide_layouts[6])
            slide.shapes.add_textbox(0, 0, Inches(3), Inches(1)).text = text
        stream = io.BytesIO()
        deck.save(stream)
        result = conversion.extract(stream.getvalue(), ".pptx", False)
        self.assertEqual([s["text"] for s in result["sections"]], ["first", "second"])
        self.assertEqual(result["sections"][1]["position"], "slide 2")

    def test_blank_pdf_is_incomplete_without_ocr(self):
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        stream = io.BytesIO()
        writer.write(stream)
        result = conversion.extract(stream.getvalue(), ".pdf", False)
        self.assertEqual(result["quality"], "incomplete")
        self.assertEqual(result["unread_sections"], ["page 1"])
        self.assertEqual(result["coverage"]["ocr"], "not run")

    def test_empty_documents_are_incomplete(self):
        for value, suffix in [(PdfWriter(), ".pdf"), (Presentation(), ".pptx")]:
            stream = io.BytesIO()
            (value.write if suffix == ".pdf" else value.save)(stream)
            self.assertEqual(conversion.extract(stream.getvalue(), suffix, False)["quality"], "incomplete")

    def test_explicit_ocr_page_preserves_embedded_text(self):
        stream = io.BytesIO()
        doc = canvas.Canvas(stream)
        doc.drawString(10, 500, "Original one")
        doc.showPage()
        doc.drawString(10, 500, "Garbled two")
        doc.save()
        recognized = {"pages": [{"page": 2, "lines": [{"text": "Corrected two", "confidence": 0.9, "box": [0, 0, 1, 1]}]}]}
        with patch.object(conversion.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(recognized))) as run:
            result = conversion.extract(stream.getvalue(), ".pdf", False, [2])
        self.assertEqual(run.call_args.args[0][-1], "2")
        self.assertIn("Original one", result["sections"][0]["text"])
        self.assertEqual(result["sections"][1]["text"], "Corrected two")
        self.assertIn("Garbled two", result["sections"][1]["embedded_text"])
        with self.assertRaises(ValueError):
            conversion.extract(stream.getvalue(), ".pdf", False, [3])

    def test_html_does_not_execute_or_fetch(self):
        html = b'<nav>noise</nav><main><h1>Title</h1><p>Body</p><script>BAD</script><img src="http://127.0.0.1/" alt="figure"></main>'
        result = conversion.extract(html, ".html", False)
        text = result["sections"][0]["text"]
        self.assertIn("# Title", text)
        self.assertIn("Body", text)
        self.assertNotIn("noise", text)
        self.assertNotIn("BAD", text)
        self.assertEqual(result["coverage"]["image_count"], 1)

    def test_hash_path_and_native_input_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "test.html"
            path.write_text("<p>Safe</p>")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            args = (root, "test.html", digest, "local:test", "2026-10-15T00:00:00Z")
            raw, result = conversion.convert(*args)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
            self.assertEqual(path.read_bytes(), raw)
            with self.assertRaises(ValueError):
                conversion.convert(root, "test.html", "0" * 64, args[3], args[4])
            with self.assertRaises(conversion.snapshot.SnapshotError):
                conversion.convert(root, "../test.html", digest, args[3], args[4])
            link = root / "link.html"
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                conversion.convert(root, "link.html", digest, args[3], args[4])
            with self.assertRaises(ValueError):
                conversion.extract(b"native Markdown", ".md", False)
            self.assertEqual(result["source_sha256"], digest)


if __name__ == "__main__":
    unittest.main()
