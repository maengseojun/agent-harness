#!/usr/bin/env python3
"""Convert one selected local source to a review bundle; never write vault notes."""

import argparse
from datetime import datetime
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

import source_snapshot as snapshot
import sync_project
import vault_drive


MAX_BYTES = 50 * 1024 * 1024
LIMITS = ["Derived text requires source review before wiki claims.",
          "Images, charts, equations and complex/merged tables require rendered source review; extraction is not a fidelity guarantee."]


def table(rows):
    rows = [[str(c).replace("|", "\\|").replace("\n", "<br>") for c in row] for row in rows]
    if not rows:
        return ""
    width = max(map(len, rows))
    rows = [row + [""] * (width - len(row)) for row in rows]
    return "\n".join(["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"] +
                     ["| " + " | ".join(row) + " |" for row in rows[1:]])


BOILERPLATE_TAGS = {"script", "style", "nav", "footer", "noscript", "header", "aside", "form", "iframe", "svg", "button", "template", "dialog"}
BOILERPLATE_ATTR = re.compile(r"(?i)(?:^|[\s_-])(?:nav|navbar|menu|sidebar|comments?|ads?|advert\w*|banner|promo\w*|share|social|related|cookie\w*|newsletter|subscribe|footer|breadcrumbs?)(?:$|[\s_-])")
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
BLOCK_TAGS = {"address", "article", "aside", "blockquote", "div", "dl", "fieldset", "figure", "footer", "form", "h1", "h2", "h3",
              "h4", "h5", "h6", "header", "hr", "main", "nav", "ol", "p", "pre", "section", "table", "ul"}
# HTML lets these end without a closing tag when one of the listed tags opens.
IMPLIED_END = {"p": BLOCK_TAGS, "li": {"li"}, "dt": {"dt", "dd"}, "dd": {"dt", "dd"}, "option": {"option"},
               "tr": {"tr"}, "td": {"td", "th", "tr"}, "th": {"td", "th", "tr"}}

SCOPE_TAGS = {"ul", "ol", "dl", "table", "select", "main", "article", "section", "body", "html"}


class LocalHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.body = []  # text inside <main>/<article>; used instead of parts when the page has one
        self.stack = []  # open elements as (tag, skipped); a boilerplate element skips everything inside it
        self.images = 0
        self.tables = 0

    @property
    def skip(self):
        return bool(self.stack) and self.stack[-1][1]

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.close_implied(tag)
        skipped = self.skip or tag in BOILERPLATE_TAGS or bool(BOILERPLATE_ATTR.search(" ".join(filter(None, (attrs.get("id"), attrs.get("class"), attrs.get("role"))))))
        if tag not in VOID_TAGS:
            self.stack.append((tag, skipped))
        if skipped:
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.emit("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in {"p", "div", "section", "article", "main", "br", "tr"}:
            self.emit("\n")
        elif tag == "li":
            self.emit("\n- ")
        elif tag in {"td", "th"}:
            self.emit(" | ")
        elif tag == "img":
            self.images += 1
            self.emit(" [image: " + attrs.get("alt", "unread") + "] ")
        elif tag == "table":
            self.tables += 1
        elif tag == "a":
            href = attrs.get("href", "")
            if href.startswith(("https://", "http://", "#", "/")):
                self.emit(" [link: " + href + "] ")

    def close_implied(self, tag):
        # Close the nearest open element this tag ends, through unclosed children, but not past a list/table/section scope.
        for index in range(len(self.stack) - 1, -1, -1):
            open_tag = self.stack[index][0]
            if tag in IMPLIED_END.get(open_tag, ()):
                del self.stack[index:]
                return self.close_implied(tag)
            if open_tag in SCOPE_TAGS:
                return

    def handle_endtag(self, tag):
        tags = [t for t, _ in self.stack]
        if tag not in tags:
            return
        index = len(tags) - 1 - tags[::-1].index(tag)
        if not self.stack[index][1] and tag in {"p", "section", "article", "main", "table"}:
            self.emit("\n")
        del self.stack[index:]  # closes unclosed children too

    def handle_data(self, data):
        if not self.skip:
            self.emit(data)

    def emit(self, text):
        self.parts.append(text)
        if any(t in {"main", "article"} for t, _ in self.stack):
            self.body.append(text)

    def text(self):
        return "".join(self.body or self.parts)


def extract(raw, suffix, ocr, ocr_pages=()):
    coverage = {"images": "not interpreted", "formulas": "not verified", "tables": "not verified", "ocr": "not run"}
    sections, limits = [], list(LIMITS)
    if suffix in {".docx", ".pptx"}:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(x.file_size for x in archive.infolist()) > 200 * 1024 * 1024 or any(x.flag_bits & 1 for x in archive.infolist()):
                raise ValueError("Office archive expanded-size limit or encryption")
    if suffix == ".docx":
        from docx import Document
        from docx.table import Table
        doc = Document(io.BytesIO(raw))
        blocks = []
        for block in doc.iter_inner_content():
            if isinstance(block, Table):
                blocks.append(table([[c.text for c in row.cells] for row in block.rows]))
            else:
                style = block.style.name if block.style else ""
                match = re.fullmatch(r"Heading ([1-6])", style)
                blocks.append(("#" * int(match[1]) + " " if match else "") + block.text)
        sections = [{"position": "document flow (not paginated)", "text": "\n\n".join(blocks)}]
        coverage.update(tables=f"{len(doc.tables)} top-level tables extracted; merged/nested review required",
                        image_count=len(doc.inline_shapes))
        limits.append("Word page numbers, headers, footers, comments, tracked changes, floating text and footnotes are not covered.")
    elif suffix == ".pptx":
        from pptx import Presentation
        deck = Presentation(io.BytesIO(raw))
        for number, slide in enumerate(deck.slides, 1):
            blocks = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    blocks.append(shape.text)
                elif shape.has_table:
                    blocks.append(table([[c.text for c in row.cells] for row in shape.table.rows]))
            sections.append({"position": f"slide {number}", "text": "\n\n".join(blocks)})
        coverage["tables"] = "top-level slide tables extracted; merged cells require review"
        limits.append("PPT group shapes, notes, charts, animations and visual reading order are not covered.")
    elif suffix == ".pdf":
        from pypdf import PdfReader
        pdf = PdfReader(io.BytesIO(raw))
        if pdf.is_encrypted or len(pdf.pages) > 100:
            raise ValueError("Encrypted PDF or page limit exceeded")
        texts = [page.extract_text() or "" for page in pdf.pages]
        selected = set(ocr_pages)
        if any(type(n) is not int or n < 1 or n > len(texts) for n in selected):
            raise ValueError("OCR page selection is outside this PDF")
        if ocr:
            selected.update(n for n, text in enumerate(texts, 1) if not text.strip())
        recognized = {}
        if selected:
            with tempfile.TemporaryDirectory(prefix="obsidian-conversion-") as temp:
                local = Path(temp) / "selected.pdf"
                local.write_bytes(raw)
                result = subprocess.run(["/usr/bin/swift", str(Path(__file__).with_name("ocr_pdf.swift")), str(local),
                                         ",".join(map(str, sorted(selected)))],
                                        capture_output=True, text=True, timeout=180)
                if result.returncode:
                    raise ValueError("Local Vision OCR failed: " + result.stderr[-1200:])
                recognized = {p["page"]: p for p in json.loads(result.stdout)["pages"]}
                if set(recognized) != selected:
                    raise ValueError("Local Vision OCR returned different pages than selected")
            coverage["ocr"] = "macOS Vision; explicitly selected/blank-text pages; output unreviewed"
            coverage["ocr_pages"] = sorted(selected)
        for number, text in enumerate(texts, 1):
            record = {"position": f"page {number}", "method": "embedded text", "text": text}
            if number in selected or not text.strip():
                lines = recognized.get(number, {}).get("lines", [])
                record.update(method="local OCR" if number in recognized else "unread scan", text="\n".join(x["text"] for x in lines), ocr_lines=lines, embedded_text=text)
            sections.append(record)
        limits.append("OCR text, line order, tables and mathematics require rendered-page comparison; nonblank pages may still contain unread images.")
    elif suffix in {".html", ".htm"}:
        parser = LocalHTML()
        parser.feed(raw.decode("utf-8"))
        sections = [{"position": "HTML document order", "text": re.sub(r"\n{3,}", "\n\n", parser.text()).strip()}]
        coverage.update(image_count=parser.images, tables=f"{parser.tables} tables as delimited cell text")
        limits.append("Local HTML only: no JavaScript, remote fetch or asset download; keeps <main>/<article> when present and drops nav/header/footer/aside/form/script/style and menu/sidebar/comment/ad/share/related/cookie blocks by id/class/role. CSS-hidden text and pages without semantic markup are not fully isolated.")
    else:
        raise ValueError("Supported local formats: .docx .pptx .pdf .html .htm; native MD/body must use native capture")
    unread = [x["position"] for x in sections if not x["text"].strip()]
    return {"sections": sections, "coverage": coverage, "limits": limits, "unread_sections": unread,
            "quality": "incomplete" if unread or not sections else "extracted-unreviewed"}


def convert(source_root, relative, expected_sha256, origin, fetched_at, *, ocr=False, ocr_pages=(), pdf_engine_config=None, pdf_pages=()):
    root = Path(source_root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("source-root must be an existing absolute directory, not a symlink")
    parts = snapshot.validate_relative_path(relative)
    if sync_project.is_sensitive(parts):
        raise ValueError("Known sensitive source path")
    source = root
    for part in parts:
        source = source / part
        if source.is_symlink():
            raise ValueError("Source symlinks are forbidden")
    raw = sync_project.read_regular_file(source, "selected source")
    if len(raw) > MAX_BYTES or snapshot.sha256(raw) != expected_sha256:
        raise ValueError("Source size limit or SHA-256 precondition mismatch")
    snapshot.clean_text(origin, "source origin")
    if not datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).tzinfo:
        raise ValueError("fetched-at needs timezone")
    if ocr_pages and source.suffix.lower() != ".pdf":
        raise ValueError("OCR page selection requires a PDF")
    if pdf_engine_config or pdf_pages:
        if not pdf_engine_config or not pdf_pages or source.suffix.lower() != ".pdf" or ocr or ocr_pages:
            raise ValueError("Advanced PDF requires runtime config and selected pages; do not combine with Vision OCR")
        import advanced_pdf
        advanced = advanced_pdf.extract(raw, pdf_pages, pdf_engine_config)
        extracted = extract(raw, ".pdf", False)
        selected = {s["position"]: s for s in advanced["sections"]}
        extracted["sections"] = [selected.get(s["position"], s) for s in extracted["sections"]]
        extracted["engine"] = advanced["engine"]
        extracted["coverage"].update(ocr="MinerU local; selected pages only; unreviewed", ocr_pages=sorted(pdf_pages),
                                     tables="HTML tables with row/column spans; source review required", formulas="LaTeX; source review required")
        extracted["limits"].append("Advanced images remain in the original PDF; placeholders replace embedded images. Unselected pages retain embedded text only. No universal table/formula fidelity guarantee.")
        extracted["unread_sections"] = [s["position"] for s in extracted["sections"] if not s["text"].strip()]
        extracted["quality"] = "incomplete" if extracted["unread_sections"] else "extracted-unreviewed"
    else:
        extracted = extract(raw, source.suffix.lower(), ocr, ocr_pages)
    body = "\n\n".join(f"## {x['position']}\n\n{x['text']}" for x in extracted["sections"]) + "\n"
    receipt = {"schema": 1, "source": origin, "source_path": str(source), "fetchedAt": fetched_at,
               "source_sha256": expected_sha256, "derived_sha256": snapshot.sha256(body.encode()),
               "converter_sha256": snapshot.sha256(Path(__file__).read_bytes() + Path(__file__).with_name("ocr_pdf.swift").read_bytes() + Path(__file__).with_name("advanced_pdf.py").read_bytes()),
               **extracted, "body": body}
    return raw, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--fetched-at", required=True)
    parser.add_argument("--ocr", action="store_true", help="Explicit local macOS Vision OCR for blank PDF pages")
    parser.add_argument("--ocr-pages", nargs="+", type=int, default=[], help="Explicit 1-based PDF pages to OCR instead of embedded text; preserve both")
    parser.add_argument("--pdf-engine-config", help="Trusted installed local MinerU runtime/model manifest; never use an incoming document as runtime config")
    parser.add_argument("--pdf-pages", nargs="+", type=int, default=[], help="Explicit 1-based pages for the advanced local PDF engine")
    parser.add_argument("--apply", action="store_true", help="Preserve the original on Drive, derived .body and receipt .json in the vault; no notes")
    parser.add_argument("--vault", default=str(snapshot.EXPECTED_VAULT))
    parser.add_argument("--drive", default=str(vault_drive.DRIVE_ROOT), help="Drive vault-offload root for the original")
    args = parser.parse_args()
    try:
        raw, receipt = convert(args.source_root, args.path, args.sha256, args.origin, args.fetched_at, ocr=args.ocr, ocr_pages=args.ocr_pages, pdf_engine_config=args.pdf_engine_config, pdf_pages=args.pdf_pages)
        paths, created = {}, []
        if args.apply:
            vault = snapshot.validate_vault(args.vault)
            key = snapshot.sha256(snapshot.json_bytes(receipt))
            base = f"raw/native-captures/conversions/{receipt['source_sha256']}/{key}"
            paths = {"raw": base + "/original" + Path(args.path).suffix.lower(), "derived": base + "/converted.body", "receipt": base + "/receipt.json"}
            # Originals (Office/PDF binaries, full web pages) live on Drive; the vault keeps only the text bundle.
            paths["raw"] = vault_drive.store(paths["raw"], raw, args.drive)
            for kind, data in [("derived", receipt["body"].encode()), ("receipt", snapshot.json_bytes(receipt))]:
                snapshot.write_immutable(vault, paths[kind], data, created)
        print(json.dumps({"ok": True, "applied": args.apply, "note_writes": 0, "created": created, "paths": paths, **receipt}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc), "note_writes": 0, "partial_files": locals().get("created", [])}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
