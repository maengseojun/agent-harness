"""pytest-only extras (plain `unittest discover` ignores this file).

- Test size, measured: every test is classified by what it actually did in this process. small = no child process;
  medium = local child processes (git, fake binaries, a real hook/CLI process); large = a real `claude`/`codex`/`gh`
  binary or the network (none today). A test marked `@pytest.mark.small` fails if it spawns anything.
  The terminal summary prints the pyramid: `test sizes: small=N medium=M large=K`.
- HARNESS_TEST_SHUFFLE=<seed>: run tests in a seeded random order (same order on every xdist worker), to find
  order dependence.
- Hermeticity: a test session id (`sess-*`) showing up in the real ~/.local/share/maeng-harness fails the run.
"""
import os
import random
import subprocess
from pathlib import Path

import pytest

LARGE_PROGS = {"claude", "codex", "gh", "curl", "wget", "ssh"}
REAL_SESSIONS = Path.home() / ".local/share/maeng-harness/sessions"

_spawned = []
_orig_init = subprocess.Popen.__init__


def _spy(self, args, *a, **kw):
    argv0 = args[0] if isinstance(args, (list, tuple)) and args else str(args).split()[0]
    _orig_init(self, args, *a, **kw)  # a program that does not exist never starts: not counted
    _spawned.append(os.path.realpath(str(argv0)) if os.sep in str(argv0) else str(argv0))


subprocess.Popen.__init__ = _spy
_sizes = {"small": 0, "medium": 0, "large": 0}


def _real_sessions():
    try:
        return {p.name for p in REAL_SESSIONS.glob("sess-*")}
    except OSError:
        return set()


def pytest_configure(config):
    config.addinivalue_line("markers", "small: must not spawn a child process (checked)")
    config._real_sessions_before = _real_sessions()


def pytest_collection_modifyitems(session, config, items):
    seed = os.environ.get("HARNESS_TEST_SHUFFLE")
    if seed:
        random.Random(seed).shuffle(items)


def size_of(spawned):
    if not spawned:
        return "small"
    # a large program is one on PATH (or anywhere) with that basename that is not a test's fake under a temp dir
    if any(os.path.basename(p) in LARGE_PROGS and not p.startswith(("/private/var/", "/var/", "/tmp/", "/private/tmp/"))
           for p in spawned):
        return "large"
    return "medium"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    _spawned.clear()
    yield
    size = size_of(list(_spawned))
    item.user_properties.append(("size", size))
    if item.get_closest_marker("small") and size != "small":
        pytest.fail(f"marked small but spawned: {sorted(set(_spawned))[:5]}", pytrace=False)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    _spawned.clear()
    yield


def pytest_runtest_logreport(report):
    if report.when == "call":
        for k, v in report.user_properties:
            if k == "size":
                _sizes[v] += 1


def pytest_sessionfinish(session, exitstatus):
    leaked = _real_sessions() - getattr(session.config, "_real_sessions_before", set())
    if leaked and not hasattr(session.config, "workerinput"):
        session.config._leaked = sorted(leaked)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if any(_sizes.values()):
        terminalreporter.write_line("test sizes: " + " ".join(f"{k}={v}" for k, v in _sizes.items()))
    if getattr(config, "_leaked", None):
        terminalreporter.write_line(f"HERMETICITY: test sessions written to the real {REAL_SESSIONS}: "
                                    f"{config._leaked[:5]}", red=True)
