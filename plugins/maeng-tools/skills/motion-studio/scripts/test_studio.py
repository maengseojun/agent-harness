"""Runs the node tests of studio.mjs under pytest, so the run is recorded as runner evidence."""
import pathlib
import subprocess


def test_studio_node_suite():
    here = pathlib.Path(__file__).parent
    r = subprocess.run(['node', '--test', str(here / 'test' / 'studio.test.mjs')], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert '# fail 0' in r.stdout and '# pass 5' in r.stdout, r.stdout[-1500:]
