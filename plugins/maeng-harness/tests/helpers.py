"""Shared fixtures: hermetic HOME/MAENG_* env, temp git repos with a local bare remote, hook/CLI runners."""
import json
import os
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


def run(cmd, cwd=None, env=None, check=True, input_text=None):
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, input=input_text)
    if check and proc.returncode != 0:
        raise AssertionError(f"{cmd} failed ({proc.returncode}): {proc.stdout}{proc.stderr}")
    return proc


class HarnessCase(unittest.TestCase):
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
            "PATH": os.environ["PATH"], "HOME": str(self.home), "MAENG_HOME": str(self.maeng_home),
            "MAENG_CACHE_DIR": str(self.cache), "MAENG_VAULT": str(self.vault), "MAENG_ETA_ROOT": str(self.eta_root),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(self.home / ".gitconfig"),
            "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.com",
            "MAENG_NOTION_DBS": "db111111111111111111111111111111",
            # Existing review tests exercise the codex backend with a fake binary; claude-backend tests opt in.
            "MAENG_REVIEW_BACKEND": "codex",
            # `maeng-review store` and fixture receipts are test-only; tests of the default policy pop this.
            "MAENG_TEST_FIXTURES": "1",
        }
        patcher = unittest.mock.patch.dict(os.environ, self.env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.sid = "sess-" + uuid.uuid4().hex[:8]

    # ---- git fixtures
    def git(self, cwd, *args, check=True):
        return run(["git", *args], cwd=cwd, env=self.env, check=check)

    def make_repo(self, name="repo", with_remote=True, files=None):
        repo = self.tmp / name
        repo.mkdir()
        self.git(repo, "init", "-q", "-b", "main")
        files = files or {"app.py": "print('hi')\n", "README.md": "# r\n", "requirements.txt": "pytest\n"}
        for rel, text in files.items():
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-qm", "init")
        if with_remote:
            remote = self.tmp / f"{name}-remote.git"
            self.git(self.tmp, "init", "-q", "--bare", "-b", "main", str(remote))
            self.git(repo, "remote", "add", "origin", str(remote))
            self.git(repo, "push", "-q", "origin", "main")
            self.git(repo, "fetch", "-q", "origin")
            self.git(repo, "remote", "set-head", "origin", "main")  # push gating needs the remote's default branch
        return repo

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
        proc = run([sys.executable, str(HOOK)], env=self.env, input_text=json.dumps(payload), check=False)
        out = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, out, proc.stderr

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
        return run([sys.executable, str(BIN / name), *args], cwd=cwd, env=env, check=check)

    def verify_tree(self, repo, command="pytest -q"):
        """Run one passing recognized check so the current tree is ship-verified."""
        self.run_check(repo, command, ok=True)


import unittest.mock  # noqa: E402  (after class body for readability)
