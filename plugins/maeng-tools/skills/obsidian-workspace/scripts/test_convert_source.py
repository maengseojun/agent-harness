import hashlib
import io
import os
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
    def test_advanced_pdf_keeps_unselected_pages_and_provenance(self):
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.add_blank_page(width=200, height=200)
        stream = io.BytesIO()
        writer.write(stream)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "test.pdf"
            path.write_bytes(stream.getvalue())
            advanced = {"sections": [{"position": "page 2", "text": "$$x^2$$", "embedded_text": "", "omitted_images": 0}], "engine": {"pages": [2]}}
            with patch("advanced_pdf.extract", return_value=advanced):
                raw, receipt = conversion.convert(root, path.name, hashlib.sha256(path.read_bytes()).hexdigest(), "synthetic:advanced", "2026-10-15T00:00:00Z", pdf_engine_config="trusted.json", pdf_pages=[2])
            self.assertEqual(raw, path.read_bytes())
            self.assertEqual(receipt["unread_sections"], ["page 1"])
            self.assertEqual(receipt["quality"], "incomplete")
            self.assertEqual(receipt["engine"]["pages"], [2])
            with self.assertRaises(ValueError):
                conversion.convert(root, path.name, hashlib.sha256(raw).hexdigest(), "synthetic:advanced", "2026-10-15T00:00:00Z", ocr=True, pdf_engine_config="trusted.json", pdf_pages=[2])

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

    def test_web_capture_keeps_body_markdown_and_sends_original_to_drive(self):
        page = (b'<html><head><title>T</title></head><body><header>Site logo</header>'
                b'<nav><a href="/">Home</a></nav><div class="sidebar">Popular posts</div>'
                b'<div id="ad-slot">Buy now</div><article><h1>Real title</h1><p>Real body.</p>'
                b'<section class="comments">First!</section></article>'
                b'<aside>Related</aside><footer>Copyright</footer></body></html>')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            src, vault, drive = root / "src", root / "vault", root / "drive"
            for d in (src, vault, drive):
                d.mkdir()
            (src / "page.html").write_bytes(page)
            digest = hashlib.sha256(page).hexdigest()
            argv = ["convert_source.py", "--source-root", str(src), "--path", "page.html", "--sha256", digest,
                    "--origin", "https://example.com/post", "--fetched-at", "2026-10-21T00:00:00Z",
                    "--apply", "--vault", str(vault), "--drive", str(drive)]
            out = io.StringIO()
            with patch.object(conversion.snapshot, "EXPECTED_VAULT", vault), patch("sys.argv", argv), redirect_stdout(out):
                self.assertEqual(conversion.main(), 0)
            result = json.loads(out.getvalue())
            body = result["body"]
            self.assertIn("# Real title", body)
            self.assertIn("Real body.", body)
            for junk in ("Site logo", "Home", "Popular posts", "Buy now", "First!", "Related", "Copyright"):
                self.assertNotIn(junk, body)
            in_vault = [p for p in vault.rglob("*") if p.is_file()]
            self.assertEqual(sorted(p.name for p in in_vault), ["converted.body", "receipt.json"])
            self.assertTrue(result["paths"]["raw"].startswith("file://"))
            stored = [p for p in drive.rglob("original.html")]
            self.assertEqual(len(stored), 1)
            self.assertEqual(hashlib.sha256(stored[0].read_bytes()).hexdigest(), digest)
            manifest = json.loads(next(drive.glob("manifest-*.json")).read_text())
            self.assertEqual(manifest[0]["sha256"], digest)
            self.assertEqual(manifest[0]["path"], stored[0].relative_to(drive).as_posix())

    def test_html_body_survives_implicitly_closed_boilerplate(self):
        html = b'<main><p class="ad">Advertisement<p>Actual article text<li class="share">Tweet<li>Point</main><p>After'
        text = conversion.extract(html, ".html", False)["sections"][0]["text"]
        self.assertIn("Actual article text", text)
        self.assertIn("Point", text)
        self.assertNotIn("Advertisement", text)
        self.assertNotIn("Tweet", text)
        self.assertNotIn("After", text)  # outside <main>
        nested = b'<main><ul><li class="share"><p>Share<li>Keep this item<ul><li>Inner<li>Inner two</ul></ul></main>'
        text = conversion.extract(nested, ".html", False)["sections"][0]["text"]
        for kept in ("Keep this item", "Inner", "Inner two"):
            self.assertIn(kept, text)
        self.assertNotIn("Share", text)
        aria = b'<main><div role="navigation">Menu links</div><div role="complementary">Aside box</div><p>Article body</p></main>'
        text = conversion.extract(aria, ".html", False)["sections"][0]["text"]
        self.assertIn("Article body", text)
        self.assertNotIn("Menu links", text)
        self.assertNotIn("Aside box", text)

    def test_drive_manifest_kept_for_each_path_of_identical_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            drive = Path(folder)
            conversion.vault_drive.store("a/x.png", b"same", drive)
            conversion.vault_drive.store("b/x.png", b"same", drive)
            paths = sorted(json.loads(m.read_text())[0]["path"] for m in drive.glob("manifest-*.json"))
            self.assertEqual(paths, ["a/x.png", "b/x.png"])

    def test_drive_refuses_symlink_out_of_root(self):
        with tempfile.TemporaryDirectory() as folder:
            drive, vault = Path(folder) / "drive", Path(folder) / "vault"
            drive.mkdir()
            (vault / "raw").mkdir(parents=True)
            (drive / "raw").symlink_to(vault / "raw")
            with self.assertRaises(ValueError):
                conversion.vault_drive.store("raw/file.pdf", b"%PDF", drive)
            self.assertEqual(list((vault / "raw").iterdir()), [])

    def test_drive_url_is_absolute_for_relative_root(self):
        with tempfile.TemporaryDirectory() as folder:
            cwd = Path.cwd()
            try:
                os.chdir(folder)
                Path("archive").mkdir()
                url = conversion.vault_drive.store("raw/f.pdf", b"%PDF", "archive")
            finally:
                os.chdir(cwd)
            self.assertTrue(url.startswith("file:///"), url)
            self.assertTrue(url.endswith("/archive/raw/f.pdf"), url)

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
