#!/usr/bin/env python3
"""Fake `gh` for staging: `pr view` prints $FAKE_GH_JSON; everything else is logged and is a no-op."""
import json
import os
import sys

a = sys.argv[1:]
log = os.environ.get("FAKE_GH_LOG")
if log:
    with open(log, "a") as f:
        f.write(json.dumps(a) + "\n")
if a[:2] == ["pr", "view"] and os.environ.get("FAKE_GH_JSON"):
    print(open(os.environ["FAKE_GH_JSON"]).read())
    sys.exit(0)
print("fake-gh: " + " ".join(a))
sys.exit(0)
