#!/usr/bin/env python3
"""One chat call to a model on the school's BAZE gateway (MAE-315). Stdlib only.

    python3 ask.py [--model gemini-4-argon] [--system TEXT] [--file PATH ...] [--max-tokens N] [PROMPT]

The prompt is PROMPT, then each --file; with neither it comes from stdin. The answer goes to stdout, the
model and tokens to stderr. Exit 1 on any failure. Nothing retries: a call can spend credit.
"""
import argparse
import json
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "decisions" / "scripts"))
import decisions_client  # noqa: E402

URL = "https://api.baze.co/v1/gateway/chat/completions/"


def ask(prompt, *, model="gemini-4-argon", system=None, max_tokens=4096, timeout=180):
    """-> (answer, response). Raises RuntimeError with a message safe to print."""
    if decisions_client.barred_from_baze(f"{system or ''}\n{prompt}"):
        raise RuntimeError("not sent: eta content does not go to BAZE (the text or the working folder is eta)")
    key = decisions_client._keychain_key("baze-api-key")
    if not key:
        raise RuntimeError("no key: store it in the keychain item baze-api-key")
    # format-based masking only: name-based masking would eat ordinary prose such as "key: value"
    clean = lambda s: decisions_client.redact(s, by_name=False)
    messages = ([{"role": "system", "content": clean(system)}] if system else []) + [{"role": "user", "content": clean(prompt)}]
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        resp = decisions_client._post(URL, {"model": model, "max_tokens": max_tokens, "messages": messages}, headers, timeout)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"http {e.code}: {clean(e.read().decode('utf-8', 'replace'))[:300]}")
    except OSError as e:  # URLError and timeouts
        raise RuntimeError(f"no response: {e}")
    try:
        answer = resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        answer = None
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("the model returned no text")
    return answer, resp


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompt", nargs="?", default="")
    ap.add_argument("--model", default="gemini-4-argon")
    ap.add_argument("--system")
    ap.add_argument("--file", action="append", default=[])
    ap.add_argument("--max-tokens", type=int, default=4096)
    a = ap.parse_args(argv)
    try:
        parts = [a.prompt] + [Path(p).read_text(encoding="utf-8") for p in a.file]
    except (OSError, UnicodeDecodeError) as e:
        print(f"ask: cannot read a file: {e}", file=sys.stderr)
        return 1
    if not a.prompt and not a.file and not sys.stdin.isatty():  # never block on an open stdin when a prompt is given
        parts.append(sys.stdin.read())
    prompt = "\n\n".join(p for p in parts if p.strip())
    if not prompt:
        ap.error("no prompt")
    try:
        answer, resp = ask(prompt, model=a.model, system=a.system, max_tokens=a.max_tokens)
    except RuntimeError as e:
        print(f"ask: {e}", file=sys.stderr)
        return 1
    print(answer.strip())
    u = resp.get("usage") or {}
    print(f"ask: {a.model}, {u.get('prompt_tokens')} in, {u.get('completion_tokens')} out", file=sys.stderr)
    if resp["choices"][0].get("finish_reason") == "length":
        print("ask: cut off at --max-tokens", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
