"""MAE-284: tree_id starts from a copy of the repo's index; the result must still be the worktree's tree."""
import os
import tempfile

from maeng import tree as treelib
from .helpers import HarnessCase, run


class TreeIdFromCopiedIndex(HarnessCase):
    def fresh_tree(self, repo):
        """Expected value from git alone: a brand-new index, `add -A`, `write-tree`."""
        with tempfile.TemporaryDirectory() as d:
            env = {**self.env, "GIT_INDEX_FILE": os.path.join(d, "index")}
            run(["git", "add", "-A"], cwd=repo, env=env)
            return run(["git", "write-tree"], cwd=repo, env=env).stdout.strip()

    def test_matches_a_fresh_index_for_every_kind_of_change(self):
        repo = self.make_repo()
        (repo / "app.py").write_text("print('changed')\n")             # modified
        (repo / "README.md").write_text("# staged\n")
        self.git(repo, "add", "README.md")
        (repo / "README.md").write_text("# staged then changed\n")     # index differs from worktree
        (repo / "requirements.txt").unlink()                           # deleted
        (repo / "new.py").write_text("x = 1\n")                        # untracked
        got, _ = treelib.tree_id(repo)
        self.assertEqual(got, self.fresh_tree(repo))
        self.assertNotEqual(got, self.git(repo, "rev-parse", "HEAD^{tree}").stdout.strip())

    def test_hidden_entries_do_not_hide_a_change(self):
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag):
                repo = self.make_repo(name="r" + flag.strip("-"))
                self.git(repo, "update-index", flag, "app.py")
                (repo / "app.py").write_text("print('hidden')\n")
                got, _ = treelib.tree_id(repo)
                self.assertEqual(got, self.fresh_tree(repo))
                self.assertNotEqual(got, self.git(repo, "rev-parse", "HEAD^{tree}").stdout.strip())

    def test_leaves_the_real_index_alone(self):
        repo = self.make_repo()
        (repo / "app.py").write_text("print('changed')\n")
        before = (repo / ".git" / "index").read_bytes()
        treelib.tree_id(repo)
        self.assertEqual((repo / ".git" / "index").read_bytes(), before)
        self.assertEqual(self.git(repo, "diff", "--cached", "--name-only").stdout, "")
