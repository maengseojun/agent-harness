import json

from maeng import evidence
from .helpers import HarnessCase
from .test_g1 import ShipBase


class Recognition(HarnessCase):
    def test_recognized_runners(self):
        yes = {"pytest -q": "pytest", "python3 -m pytest tests": "pytest", "python -m unittest discover -s t": "unittest",
               "cd sub && pytest": "pytest", "uv run pytest": "pytest", "npm test": "npm test",
               "pnpm run lint": "pnpm run lint", "yarn test": "yarn test", "npm run typecheck": "npm run typecheck",
               "npm run build": "npm run build", "forge test -vvv": "forge test", "forge build": "forge build",
               "cargo test": "cargo test", "cargo clippy --all": "cargo clippy", "cargo build": "cargo build",
               "go test ./...": "go test", "make test": "make test", "make check": "make check",
               "ruff check .": "ruff check", "mypy src": "mypy", "tsc --noEmit": "tsc",
               "claude plugin validate plugins/x": "claude plugin validate", "playwright test": "playwright test",
               "npx playwright test": "playwright test"}
        for cmd, name in yes.items():
            rec = evidence.recognize(cmd)
            self.assertIsNotNone(rec, cmd)
            self.assertEqual(rec["checks"][0][0], name, cmd)

    def test_not_recognized(self):
        for cmd in ("ls", "git status", "pytest | tail", "pytest; echo done", "pytest || true", "pytest &", "echo pytest",
                    "ruff format .", "npm install", "make", "python script.py"):
            self.assertIsNone(evidence.recognize(cmd), cmd)


class EvidenceTests(ShipBase):
    def state_evidence(self):
        return self.load_state()["evidence"]

    def test_background_and_piped_runs_give_no_evidence(self):
        self.hook("PreToolUse", self.repo, tool_name="Bash", tool_input={"command": "pytest", "run_in_background": True},
                  tool_use_id="bg")
        self.hook("PostToolUse", self.repo, tool_name="Bash", tool_input={"command": "pytest", "run_in_background": True},
                  tool_use_id="bg", tool_response={})
        self.run_check(self.repo, "pytest | tail -3")
        self.assertEqual(self.state_evidence(), [])

    def test_dirty_submodule_gives_no_evidence(self):
        sub = self.make_repo("subrepo", with_remote=False)
        self.git(self.repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "vendor/sub")
        self.commit_all(self.repo, "add submodule")
        self.verified()                                    # clean submodule: evidence is recorded
        self.assertEqual(len(self.state_evidence()), 1)
        (self.repo / "vendor/sub/app.py").write_text("print('dirty')\n")
        self.run_check(self.repo, "pytest -q")
        self.assertEqual(len(self.state_evidence()), 1)    # no new evidence while dirty
        r = self.cli("maeng-verify", ["skip", "x"], self.repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("dirty submodule", r.stderr)

    def test_default_ship_check_is_pytest_n8_not_narrowed_or_auto(self):
        def ship():
            return json.loads(self.cli("maeng-verify", ["status"], self.repo).stdout)["ship_verified"]

        self.run_check(self.repo, "python3 -m pytest -q -n 8")
        self.assertTrue(ship())                                # the default ship check passes on this tree
        for i, cmd in enumerate(("python3 -m pytest -q -k name", "python3 -m pytest -q -n auto")):
            (self.repo / f"mod{i}.py").write_text(f"X = {i}\n")
            self.commit_all(self.repo, f"change {i}")          # a new tree: earlier evidence no longer counts
            self.run_check(self.repo, cmd)
            self.assertFalse(ship(), cmd)


