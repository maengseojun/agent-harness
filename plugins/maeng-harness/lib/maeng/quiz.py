"""Merge-quiz truth: patch ids, a throwaway clone, execution-backed items and keyed grading. Every keyed answer comes from
a recorded run of the project's own tests (T4); the model only proposes candidates. Nothing here touches the user's checkout."""
import os
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .common import git

CLEAN = "없음"
TIMEOUT = 300  # seconds per test run
FAIL_LINE = re.compile(r"\bFAIL(?:ED)?\b|\bfailed\b|^not ok\b", re.M)
SUMMARY = re.compile(r"^[=\s]*\d+ (?:failed|passed|error|skipped)")  # pytest's "1 failed, 5 passed in 0.1s"
TEST_FILE = re.compile(r"(^|/)(tests?/|test_[^/]*$)|_test\.[^/]*$|\.(?:test|spec)\.[^/]*$")
MAX_LINES = 3  # a mutation is a find/replace of at most this many lines


def patch_id(cwd, base, head):
    """The stable patch id of base...head, equal across a rebase that keeps the diff; None when it cannot be read."""
    rc, diff, _ = git(cwd, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", f"{base}...{head}")
    if rc != 0 or not diff:
        return None
    rc, out, _ = git(cwd, "patch-id", "--stable", input_text=diff)
    return out.split()[0] if rc == 0 and out.split() else None


def clone(top):
    """A throwaway copy of the checkout -> (tmp dir to delete, path of the copy). `cp -c` clones on APFS, so
    node_modules, lib/ and build output come along (A-12); plain `cp -R` is the fallback."""
    tmp = tempfile.mkdtemp(prefix="maeng-quiz-")
    dest = os.path.join(tmp, "repo")
    for flag in ("-cR", "-R"):
        if subprocess.run(["cp", flag, top, dest], capture_output=True).returncode == 0:
            if os.path.isfile(os.path.join(dest, ".git")):  # a linked worktree's .git file points at the user's git dir
                os.unlink(os.path.join(dest, ".git"))
            return tmp, dest
        shutil.rmtree(dest, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)
    raise OSError("cannot copy the checkout")


def run_tests(cmd, cwd):
    """-> (passed, failing lines); (False, []) when the run cannot finish. No bytecode is written, so a restored
    source never meets a stale .pyc."""
    try:
        proc = subprocess.run(["sh", "-c", cmd], cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    except (OSError, subprocess.SubprocessError):
        return False, []
    lines = [FAIL_LINE.sub("", ln).strip() for ln in (proc.stdout + proc.stderr).splitlines()
             if FAIL_LINE.search(ln) and not SUMMARY.match(ln)]
    return proc.returncode == 0, [ln for ln in lines if ln]


def _lines(text):
    rows = text.split("\n")
    return rows[:-1] if rows[-1] == "" else rows  # a final newline does not start a line


def _inside(repo, path):
    """The absolute path of `path` in the clone, or None when it leaves the clone."""
    real = os.path.realpath(os.path.join(repo, path))
    return real if real.startswith(os.path.realpath(repo) + os.sep) else None


def _predict(c, repo, changed):
    """A masked literal from a passing test line, else None. The question never shows the answer."""
    path, line, literal = c.get("file"), c.get("line"), c.get("literal")
    if not (isinstance(path, str) and TEST_FILE.search(path) and isinstance(line, int) and isinstance(literal, str)
            and literal.strip() and (changed is None or path in changed)):
        return None
    try:
        rows = _lines(Path(_inside(repo, path) or "/nonexistent").read_text())
    except (OSError, UnicodeDecodeError):
        return None
    if not 1 <= line <= len(rows) or literal not in rows[line - 1]:
        return None
    asked = c.get("question") if isinstance(c.get("question"), str) and literal not in c["question"] else \
        "기대값이 가려진 테스트 줄입니다. 코드가 실제로 내는 값은 무엇입니까?"
    row, at = rows[line - 1], rows[line - 1].rindex(literal)  # the expected value is the last one on an assert line
    return {"kind": "predict", "file": path, "question": f"{asked}\n\n{path}:{line}\n{row[:at]}___{row[at + len(literal):]}",
            "key": literal, "reveal": literal}


def _defect(c, repo, cmd, changed):
    """A mutation the tests catch -> {file, changed lines, snippet window, failing lines, mutated rows}, else None."""
    path, find, new = c.get("file"), c.get("find"), c.get("replace")
    if not (isinstance(path, str) and isinstance(find, str) and isinstance(new, str) and find.strip() and find != new
            and (changed is None or path in changed) and find.count("\n") < MAX_LINES and new.count("\n") < MAX_LINES):
        return None
    target = Path(_inside(repo, path) or "/nonexistent")
    try:
        orig = target.read_text()
    except (OSError, UnicodeDecodeError):
        return None
    if orig.count(find) != 1:
        return None
    start = orig[:orig.index(find)].count("\n") + 1  # first line of the find, 1-based
    mutated = orig.replace(find, new, 1)
    target.write_text(mutated)
    try:
        ok, failing = run_tests(cmd, repo)
    finally:
        target.write_text(orig)  # restored before the next mutation
    if ok or not failing:  # the tests missed it (an equivalent or untested change), or broke before running
        return None
    before, after = _lines(find), _lines(new)
    pre = next((i for i, (x, y) in enumerate(zip(before, after)) if x != y), min(len(before), len(after)))
    post = 0
    while post < min(len(before), len(after)) - pre and before[-1 - post] == after[-1 - post]:
        post += 1
    first, last = start + pre, start + max(pre, len(after) - post - 1)  # the changed lines in the mutated file
    s, e = c.get("snippet_start"), c.get("snippet_end")
    if not (isinstance(s, int) and isinstance(e, int) and 1 <= s <= first and last <= e <= s + 40):
        s, e = max(1, first - 3), last + 3
    rows = _lines(mutated)
    return {"file": path, "changed": list(range(first, last + 1)), "window": (s, min(e, len(rows))), "failing": failing,
            "rows": rows, "orig": _lines(orig), "find_span": (start, start + len(before) - 1)}


def _shown(rows, s, e):
    return "\n".join(f"{n}: {rows[n - 1]}" for n in range(s, e + 1))


def _defect_items(d, rng):
    s, e = d["window"]
    where = d["file"]
    kind = rng.choice(["defect-line", "failing-test"])
    if kind == "failing-test":
        return {"kind": kind, "file": where, "key": d["failing"], "reveal": d["failing"][0],
                "question": f"`{where}`를 아래처럼 바꾸면 테스트가 실패합니다. 실패하는 테스트 하나의 이름을 답하세요.\n\n{_shown(d['rows'], s, e)}"}
    return {"kind": kind, "file": where, "key": {"lines": d["changed"], "file": where}, "reveal": f"{where}:{d['changed'][0]}",
            "question": _snippet_question(where, _shown(d["rows"], s, e))}


def _snippet_question(where, shown):
    return (f"`{where}`의 일부입니다. 결함이 하나 들어 있을 수 있습니다. 결함이 있는 줄(번호 또는 `파일:번호`)을 답하세요. "
            f"없으면 `{CLEAN}`.\n\n{shown}")


def _clean(d, rng):
    """The same file's untouched lines in a window of the same size, away from the mutation; answer `없음`."""
    s, e = d["window"]
    size, rows = e - s + 1, d["orig"]
    lo, hi = d["find_span"]
    starts = [n for n in range(1, len(rows) - size + 2)
              if (n + size - 1 < lo or n > hi) and any(r.strip() for r in rows[n - 1:n - 1 + size])]
    if not starts:
        return None
    n = rng.choice(starts)
    return {"kind": "defect-line", "file": d["file"], "key": {"lines": [], "file": d["file"]}, "reveal": CLEAN,
            "question": _snippet_question(d["file"], _shown(rows, n, n + size - 1))}


def confirm_items(candidates, top, test_cmd, changed=None, rng=random, want=4):
    """Keep what a run of the project's tests proves, in a throwaway clone of `top`: a masked literal from a test line
    that passes at head, and a mutation the tests catch (an equivalent or untested one is dropped). A failing suite at
    head, no test command or no clone means no truth is available: []. -> up to `want` items."""
    if not test_cmd:
        return []
    try:
        tmp, repo = clone(top)
    except OSError:
        return []
    try:
        ok, _ = run_tests(test_cmd, repo)
        if not ok:
            return []
        picked, defects = [], []
        for c in candidates:
            if c.get("kind") == "predict":
                item = _predict(c, repo, changed)
                picked += [item] if item else []
            elif c.get("kind") == "defect":
                d = _defect(c, repo, test_cmd, changed)
                defects += [d] if d else []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    items = picked + [_defect_items(d, rng) for d in defects]
    by = {id(it): d for it, d in zip(items[len(picked):], defects)}
    rng.shuffle(items)
    items = items[:want]
    lines = [it for it in items if it["kind"] == "defect-line"]
    if lines:  # one defect-line item becomes a clean snippet of the same file, so `없음` is a real answer
        swap = rng.choice(lines)
        clean = _clean(by[id(swap)], rng)
        if clean:
            items[items.index(swap)] = clean
    return items


def _same(given, key):
    def norm(x):
        return x.strip().strip("'\"").strip().casefold()
    try:
        return float(norm(given)) == float(norm(key))
    except ValueError:
        return norm(given) == norm(key)


def grade_keyed(item, answer):
    """Deterministic, no model (T4). predict: equal after strip and casefold, numbers by value. defect-line: a changed
    line as a number or `file:line`, or `없음` for a clean snippet. failing-test: a piece of a failing line.
    shortcut: any piece of 4+ characters counts (`assert` too); upgrade to test-id matching if guessing shows up."""
    a, kind, key = (answer or "").strip(), item["kind"], item["key"]
    if kind == "predict":
        return _same(a, key)
    if kind == "defect-line":
        if a.casefold() == CLEAN:
            return not key["lines"]
        m = re.fullmatch(r"(?:(.+):)?(\d+)", a)
        return bool(m) and int(m.group(2)) in key["lines"] and m.group(1) in (None, key["file"], os.path.basename(key["file"]))
    return len(a) >= 4 and any(a.casefold() in line.casefold() for line in key)
