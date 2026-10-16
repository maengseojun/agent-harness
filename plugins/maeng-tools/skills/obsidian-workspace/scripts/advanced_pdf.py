"""Optional pinned local MinerU route; runtime configuration is trusted operator input."""

import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


VERSION = "4.0.12"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def obsidian_text(text):
    # MathJax inside an HTML algorithm container is not ordinary Markdown math.
    text = re.sub(r'<div class="docvortex-algorithm"[^>]*>(.*?)</div>', r'\1', text, flags=re.S).strip()
    text, images = re.subn(r'!\[[^\]\r\n]*\]\(\s*data:image/[^)\r\n]+\)',
                          "[Image retained in original PDF; not interpreted]", text, flags=re.I)
    if re.search(r"data:image", text, flags=re.I):
        raise ValueError("Unexpected inline image representation; inspect the original PDF")
    return text, images


def extract(raw, pages, config_path):
    from pypdf import PdfReader, PdfWriter
    config_path = Path(config_path)
    if not config_path.is_absolute() or config_path.is_symlink() or config_path.stat().st_size > 1024 * 1024:
        raise ValueError("Use an absolute trusted local runtime configuration file")
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    if config.get("engine") != "mineru" or config.get("version") != VERSION:
        raise ValueError("Advanced PDF requires the reviewed MinerU 4.0.12 runtime")
    python, home = Path(config["python"]), Path(config["model_home"])
    if not python.is_absolute() or not python.is_file() or not os.access(python, os.X_OK) or not home.is_absolute() or not home.is_dir():
        raise ValueError("Missing absolute local engine interpreter or model directory")
    models = config["models"]
    if not isinstance(models, list) or not models:
        raise ValueError("Pinned model manifest required")
    for model in models:
        relative = Path(model["path"])
        if relative.is_absolute() or ".." in relative.parts or digest(home / relative) != model["sha256"]:
            raise ValueError("Model artifact hash mismatch")
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted or len(reader.pages) > 100 or not pages or len(set(pages)) != len(pages) or any(type(n) is not int or not 1 <= n <= len(reader.pages) for n in pages):
        raise ValueError("Select unique valid 1-based advanced PDF pages (PDF limit: 100)")
    pages = sorted(pages)
    with tempfile.TemporaryDirectory(prefix="obsidian-advanced-pdf-") as folder:
        root = Path(folder)
        selected, output = root / "selected.pdf", root / "result.json"
        writer = PdfWriter()
        for number in pages:
            writer.add_page(reader.pages[number - 1])
        with selected.open("xb") as target:
            writer.write(target)
        isolated_config = root / "mineru.yaml"
        isolated_config.write_text("{}\n")
        env = {k: v for k, v in os.environ.items() if not k.startswith("MINERU_") and k not in {"PYTHONPATH", "PYTHONHOME"}}
        env.update(MINERU_HOME=str(home), MINERU_CONFIG=str(isolated_config), MINERU_MODEL_SOURCE="local",
                   MINERU_MODEL_SMALL_BACKEND="onnx", MINERU_MODEL_VLM_ENGINE="llama-cpp", HF_HUB_OFFLINE="1")
        result = subprocess.run([str(python), "-I", str(Path(__file__).resolve()), str(selected), str(output), str(config_path)],
                                env=env, capture_output=True, text=True, timeout=1800)
        if result.returncode or not output.is_file() or output.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("Local advanced PDF failed: " + result.stderr[-1200:])
        actual = json.loads(output.read_text())
    if actual.get("version") != VERSION or [p["page"] for p in actual["pages"]] != list(range(1, len(pages) + 1)):
        raise ValueError("Engine version or selected-page coverage mismatch")
    sections = []
    for number, page in zip(pages, actual["pages"]):
        if not isinstance(page["text"], str) or type(page["image_count"]) is not int or page["image_count"] < 0:
            raise ValueError("Malformed engine page result")
        sections.append({"position": f"page {number}", "method": "MinerU local OCR/layout/formula",
                         "text": page["text"], "embedded_text": reader.pages[number - 1].extract_text() or "",
                         "omitted_images": page["image_count"]})
    return {"sections": sections, "engine": {"name": "mineru", "version": VERSION,
            "config_sha256": hashlib.sha256(config_bytes).hexdigest(), "models": models,
            "tier": "standard", "ocr_mode": "ocr", "small_backend": "onnx", "vlm_engine": "llama-cpp",
            "remote_services": False, "image_analysis": False, "pages": pages}}


def worker(source, output, config_path):
    from importlib.metadata import version
    if version("mineru") != VERSION:
        raise ValueError("Installed MinerU version differs from pinned runtime")
    from mineru.model.registry import small_model_repo, vlm_model_repo
    pinned = {entry["path"] for entry in json.loads(Path(config_path).read_text())["models"]}
    required = {str(Path("models") / repo.local_name / relative)
                for repo in (small_model_repo("onnx"), vlm_model_repo("llama-cpp")) for relative in repo.paths.values()}
    if not required.issubset(pinned):
        raise ValueError("Model manifest omits required engine artifacts")
    from mineru.parser import parse
    from mineru.parser.base import ParseResult
    result = parse(Path(source), tier="standard", ocr_mode="ocr", image_analysis=False, page_range="all")
    pages = []
    for page in result.pages:
        image_count = 0

        def image_placeholder(block):
            nonlocal image_count
            image_count += 1
            return "[Image retained in original PDF; not interpreted]"

        middle = result.middle_json.model_copy(update={"pages": [page], "is_full_document": False})
        text = ParseResult(middle_json=middle).markdown(image_renderer=image_placeholder)
        text, inline_images = obsidian_text(text)
        pages.append({"page": page.page_idx + 1, "text": text, "image_count": image_count + inline_images})
    Path(output).write_text(json.dumps({"version": VERSION, "pages": pages}, ensure_ascii=False))


if __name__ == "__main__":
    worker(*sys.argv[1:])
