"""Shared fixtures: hermetic HOME/MAENG_* env, temp git repos with a local bare remote, hook/CLI runners.

Hooks and CLIs run in-process by default (same code path as `maeng_hooks.main()` / the bin script's `main()`, with
stdin/stdout/env/cwd swapped). A test class sets `PROCESS = True` (or the run sets HARNESS_TEST_PROCESS=1) to spawn
them as real processes; tests/test_boundary.py does that for the entry points."""
import atexit
import contextlib
import importlib.util
import io
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "maeng_hooks.py"
BIN = ROOT / "bin"
sys.path.insert(0, str(ROOT / "lib"))
FORCE_PROCESS = os.environ.get("HARNESS_TEST_PROCESS") == "1"


def run(cmd, cwd=None, env=None, check=True, input_text=None):
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, input=input_text)
    if check and proc.returncode != 0:
        raise AssertionError(f"{cmd} failed ({proc.returncode}): {proc.stdout}{proc.stderr}")
    return proc


def _git_dir():
    """A directory holding only `git` -> the real git binary. On macOS /usr/bin/git is an xcrun shim that costs
    ~8 ms per call; its real directory also holds python3, so it is not put on PATH itself. git finds its helpers
    (`git submodule`, templates) relative to its own path, so libexec/ and share/ are mirrored next to bin/."""
    git = shutil.which("git")
    if sys.platform != "darwin" or git != "/usr/bin/git":
        return None
    try:
        real = subprocess.run(["xcrun", "-f", "git"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not (real and os.access(real, os.X_OK)):
        return None
    d = Path(tempfile.mkdtemp(prefix="maeng-gitbin-"))
    atexit.register(shutil.rmtree, d, ignore_errors=True)
    prefix = Path(real).parent.parent
    (d / "bin").mkdir()
    (d / "bin" / "git").symlink_to(real)
    for sub in ("libexec", "share"):
        if (prefix / sub).is_dir():
            (d / sub).symlink_to(prefix / sub)
    return str(d / "bin")


GIT_DIR = _git_dir()
TEST_PATH = f"{GIT_DIR}:{os.environ['PATH']}" if GIT_DIR else os.environ["PATH"]

_TEMPLATES = {}
_TEMPLATE_ROOT = None


def _template_root():
    global _TEMPLATE_ROOT
    if _TEMPLATE_ROOT is None:
        _TEMPLATE_ROOT = Path(tempfile.mkdtemp(prefix="maeng-tpl-")).resolve()
        atexit.register(shutil.rmtree, _TEMPLATE_ROOT, ignore_errors=True)
    return _TEMPLATE_ROOT


_hook_module = None


def _hook_main():
    global _hook_module
    if _hook_module is None:
        spec = importlib.util.spec_from_file_location("maeng_hooks_inproc", HOOK)
        _hook_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_hook_module)
    return _hook_module.main


class _Stream(io.TextIOWrapper):
    """Text stream with a `.buffer` (some CLIs write raw bytes) whose text is read back with getvalue()."""

    def __init__(self):
        super().__init__(io.BytesIO(), encoding="utf-8", write_through=True)

    def getvalue(self):
        self.flush()
        return self.buffer.getvalue().decode("utf-8", errors="replace")


@contextlib.contextmanager
def _swapped(env, cwd=None, stdin_text=""):
    """Run code as if it were a child process: environment, cwd, argv-free stdio. Yields (stdout, stderr)."""
    out, err = _Stream(), _Stream()
    old_cwd, old_path = os.getcwd(), list(sys.path)
    old_stdin, old_stdout, old_stderr = sys.stdin, sys.stdout, sys.stderr
    with unittest.mock.patch.dict(os.environ, env, clear=True):
        try:
            if cwd is not None:
                os.chdir(cwd)
            sys.stdin, sys.stdout, sys.stderr = io.StringIO(stdin_text), out, err
            yield out, err
        finally:
            sys.stdin, sys.stdout, sys.stderr = old_stdin, old_stdout, old_stderr
            os.chdir(old_cwd)
            sys.path[:] = old_path


def _exit_code(exc):
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    print(code, file=sys.stderr)  # sys.exit("msg"): message on stderr, status 1
    return 1


def call_hook(env, text):
    """In-process `maeng_hooks.py` with `text` on stdin -> CompletedProcess."""
    with _swapped(env, stdin_text=text) as (out, err):
        try:
            rc = _hook_main()()
        except SystemExit as exc:
            rc = _exit_code(exc)
        rc = rc or 0
    return subprocess.CompletedProcess([str(HOOK)], rc, out.getvalue(), err.getvalue())


def call_cli(name, args, cwd, env):
    """In-process bin/<name> run as __main__ -> CompletedProcess."""
    with _swapped(env, cwd=cwd) as (out, err):
        old_argv = sys.argv
        sys.argv = [str(BIN / name), *args]
        try:
            runpy.run_path(str(BIN / name), run_name="__main__")
            rc = 0
        except SystemExit as exc:
            rc = _exit_code(exc)
        finally:
            sys.argv = old_argv
    return subprocess.CompletedProcess([name, *args], rc, out.getvalue(), err.getvalue())


class HarnessCase(unittest.TestCase):
    PROCESS = False  # True: hooks and CLIs run as real child processes

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="maeng-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.maeng_home = self.tmp / "maeng-home"
        self.cache = self.tmp / "cache"
        self.vault = self.tmp / "vault"
        self.eta_root = self.tmp / "eta_v1"
        self.home.mkdir()
        self.vault.mkdir()
        self.env = {
            "PATH": TEST_PATH, "HOME": str(self.home), "MAENG_HOME": str(self.maeng_home),
            "MAENG_CACHE_DIR": str(self.cache), "MAENG_VAULT": str(self.vault), "MAENG_ETA_ROOT": str(self.eta_root),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(self.home / ".gitconfig"),
            "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.com",
            "MAENG_NOTION_DBS": "db111111111111111111111111111111",
            # Existing review tests exercise the codex backend with a fake binary; claude-backend tests opt in.
            "MAENG_REVIEW_BACKEND": "codex",
            # Parent reviews try claude (Fable) first; never reach the real CLI from a test.
            "MAENG_CLAUDE": str(self.tmp / "no-claude"),
            # `maeng-review store` and fixture receipts are test-only; tests of the default policy pop this.
            "MAENG_TEST_FIXTURES": "1",
            # Decisions checks are off so no test reaches the API; test_decisions_wiring turns them on.
            "MAENG_DECISIONS": "off",
        }
        patcher = unittest.mock.patch.dict(os.environ, self.env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.sid = "sess-" + uuid.uuid4().hex[:8]

    # ---- git fixtures
    def git(self, cwd, *args, check=True):
        return run(["git", *args], cwd=cwd, env=self.env, check=check)

    def make_repo(self, name="repo", with_remote=True, files=None):
        """A repo with one commit (and a bare `origin` holding it). Built once per process per file set, then
        copied: the copy is byte-identical to a fresh build except for the remote path, which is rewritten."""
        files = files or {"app.py": "print('hi')\n", "README.md": "# r\n", "requirements.txt": "pytest\n"}
        key = (tuple(sorted(files.items())), with_remote)
        tpl = _TEMPLATES.get(key)
        if tpl is None:
            tpl = _template_root() / f"t{len(_TEMPLATES)}"
            tpl.mkdir()
            self._build_repo(tpl, "repo", with_remote, files)
            _TEMPLATES[key] = tpl
        repo = self.tmp / name
        shutil.copytree(tpl / "repo", repo, symlinks=True)
        if with_remote:
            remote = self.tmp / f"{name}-remote.git"
            shutil.copytree(tpl / "repo-remote.git", remote, symlinks=True)
            cfg = repo / ".git" / "config"
            cfg.write_text(cfg.read_text().replace(str(tpl / "repo-remote.git"), str(remote)))
        return repo

    def _build_repo(self, base, name, with_remote, files):
        repo = base / name
        repo.mkdir()
        self.git(repo, "init", "-q", "-b", "main")
        for rel, text in files.items():
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-qm", "init")
        if with_remote:
            remote = base / f"{name}-remote.git"
            self.git(base, "init", "-q", "--bare", "-b", "main", str(remote))
            self.git(repo, "remote", "add", "origin", str(remote))
            self.git(repo, "push", "-q", "origin", "main")
            self.git(repo, "fetch", "-q", "origin")
            self.git(repo, "remote", "set-head", "origin", "main")  # push gating needs the remote's default branch

    def commit_all(self, repo, msg="c"):
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-qm", msg)
        return self.git(repo, "rev-parse", "HEAD").stdout.strip()

    def head(self, repo):
        return self.git(repo, "rev-parse", "HEAD").stdout.strip()

    # ---- hook runner
    def hook(self, event, cwd, **fields):
        payload = {"hook_event_name": event, "session_id": self.sid, "cwd": str(cwd)}
        payload.update(fields)
        proc = self.run_hook_text(json.dumps(payload))
        out = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, out, proc.stderr

    def in_process(self):
        return not (self.PROCESS or FORCE_PROCESS)

    def run_hook_text(self, text):
        """Feed raw stdin text to the hook -> CompletedProcess (in-process unless PROCESS)."""
        if self.in_process():
            return call_hook(self.env, text)
        return run([sys.executable, str(HOOK)], env=self.env, input_text=text, check=False)

    def start(self, cwd):
        self.hook("SessionStart", cwd, source="startup")
        self.hook("UserPromptSubmit", cwd, prompt="go")

    def pre(self, cwd, tool, tool_input, **kw):
        """-> (denied: bool, reason)"""
        rc, out, err = self.hook("PreToolUse", cwd, tool_name=tool, tool_input=tool_input,
                                 tool_use_id=kw.pop("tool_use_id", "tu-" + uuid.uuid4().hex[:6]), **kw)
        spec = (out or {}).get("hookSpecificOutput", {})
        denied = spec.get("permissionDecision") == "deny" or rc == 2
        return denied, spec.get("permissionDecisionReason", err)

    def bash_pre(self, cwd, command):
        return self.pre(cwd, "Bash", {"command": command})

    def run_check(self, cwd, command="pytest -q", ok=True, between=None, tuid=None):
        tuid = tuid or "tu-" + uuid.uuid4().hex[:6]
        self.hook("PreToolUse", cwd, tool_name="Bash", tool_input={"command": command}, tool_use_id=tuid)
        if between:
            between()
        if ok:
            self.hook("PostToolUse", cwd, tool_name="Bash", tool_input={"command": command}, tool_use_id=tuid,
                      tool_response={"stdout": "ok", "stderr": ""})
        else:
            self.hook("PostToolUseFailure", cwd, tool_name="Bash", tool_input={"command": command},
                      tool_use_id=tuid, error="Command failed with exit code 1")

    def load_state(self):
        from maeng import state
        return state.load(self.sid)

    def cli(self, name, args, cwd, extra_env=None, check=False):
        env = {**self.env, "MAENG_SESSION_ID": self.sid, **(extra_env or {})}
        if self.in_process():
            proc = call_cli(name, args, cwd, env)
            if check and proc.returncode != 0:
                raise AssertionError(f"{name} {args} failed ({proc.returncode}): {proc.stdout}{proc.stderr}")
            return proc
        return run([sys.executable, str(BIN / name), *args], cwd=cwd, env=env, check=check)

    def verify_tree(self, repo, command="pytest -q"):
        """Run one passing recognized check so the current tree is ship-verified."""
        self.run_check(repo, command, ok=True)


import unittest.mock  # noqa: E402  (after class body for readability)
