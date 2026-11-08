"""Runs the node tests of studio.mjs under pytest, so the run is recorded as runner evidence."""
import pathlib
import re
import subprocess


def test_studio_node_suite():
    here = pathlib.Path(__file__).parent
    r = subprocess.run(['node', '--test', str(here / 'test' / 'studio.test.mjs')], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    # node 22 prints '# fail 0', node 24 'ℹ fail 0'
    assert re.search(r'(?:#|ℹ) fail 0\b', r.stdout) and re.search(r'(?:#|ℹ) pass 5\b', r.stdout), r.stdout[-1500:]
