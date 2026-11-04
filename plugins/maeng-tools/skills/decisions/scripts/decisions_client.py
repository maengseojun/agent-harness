#!/usr/bin/env python3
"""OpenAI Decisions API client for the trial week (MAE-306). Stdlib only.

decide(input, questions, pilot) -> one dict per question, in question order:
  {"name", "type", "status": "ok"|"unknown", ...}
An ok answer carries the fields of its type (choice+probabilities+confidence,
probability, or score+probabilities+confidence). An unknown answer carries
"reason": refused | missing | http_<code> | timeout | error | off | no_key
and never a verdict field; "refused" includes an off-list choice or a value out of range. Nothing about the API or the network raises;
invalid questions raise ValueError.

No request is sent when MAENG_DECISIONS=off.
Every call appends one line to the ledger (MAENG_DECISIONS_LEDGER, default
~/Documents/maeng-harness/decisions/ledger.jsonl): the input is stored as a
sha256 and a character count of the REDACTED text, never the text; the key is
never stored or printed. latency_ms and token counts are 0 when no request
was sent (outcome off, no_key).
"""
import hashlib
import json
import math
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://api.openai.com/v1/decisions"
MODEL = "gpt-6-luna"
# USD per 1M input tokens; output is not charged. Cached and cache-write
# tokens are included in input_tokens.
PRICE_INPUT, PRICE_CACHED, PRICE_WRITE = 0.10, 0.01, 0.125
# The field each question type must answer with, else the answer is not a verdict.
_FIELD = {"choice": "choice", "predicate": "probability", "score": "score"}

_R = "[REDACTED]"
_PEM = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S)
_URL_CRED = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://)[^/\s@]+@")
_AUTH = re.compile(r"(\bAuthorization[\"']?[ \t]*[:=][ \t]*)(?![ \t]|\[REDACTED\])(\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\r\n]*)", re.I)
_BEARER = re.compile(r"(\bBearer\s+)[A-Za-z0-9._~+/=-]{8,}", re.I)
_KV = re.compile(
    r"(\b[\w.-]*(?:KEY|TOKEN|SECRET|PASSWORD)[\w.-]*[\"']?[ \t]*[:=][ \t]*)(?![ \t]|\[REDACTED\])(\"[^\"\r\n]*\"|'[^'\r\n]*'|\S+)", re.I)
_TOKEN = re.compile(
    r"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_-]{8,}|gh[pos]_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{8,}"
    r"|xox[bpa]-[A-Za-z0-9-]{8,}|glpat-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16})")


def redact(text):
    """Replace secrets with [REDACTED]. Over-redacts rather than leaks (a prose
    "key: value" or "Bearer <word>" is also replaced); idempotent."""
    text = _PEM.sub(_R, text)
    text = _URL_CRED.sub(lambda m: m.group(1) + _R + "@", text)
    text = _AUTH.sub(lambda m: m.group(1) + _R, text)
    text = _BEARER.sub(lambda m: m.group(1) + _R, text)
    text = _KV.sub(lambda m: m.group(1) + _R, text)
    return _TOKEN.sub(_R, text)


def _walk(x):
    if isinstance(x, str):
        return redact(x)
    if isinstance(x, list):
        return [_walk(i) for i in x]
    if isinstance(x, dict):
        return {k: _walk(v) for k, v in x.items()}
    return x


def _keychain_key():
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", "openai-api-key", "-w"],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def _api_key():
    return os.environ.get("OPENAI_API_KEY", "").strip() or _keychain_key()


def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _call(body, key, timeout):
    """-> (reason or None, response). Every failure becomes a reason."""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        return None, _post(URL, body, headers, timeout)
    except urllib.error.HTTPError as e:
        return f"http_{e.code}", None
    except (socket.timeout, TimeoutError):
        return "timeout", None
    except urllib.error.URLError as e:
        return ("timeout" if isinstance(e.reason, (socket.timeout, TimeoutError)) else "error"), None
    except Exception:
        return "error", None


def _validate(questions):
    if not isinstance(questions, list) or not 1 <= len(questions) <= 400:
        raise ValueError("questions must be a list of 1 to 400")
    names = [q.get("name") for q in questions]
    if not all(isinstance(n, str) and n for n in names) or len(set(names)) != len(names):
        raise ValueError("every question needs a unique non-empty name")
    if any(q.get("type") not in _FIELD for q in questions):
        raise ValueError("question type must be predicate, choice or score")


def _unknown(q, reason):
    return {"name": q["name"], "type": q["type"], "status": "unknown", "reason": reason}


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _allowed(s, v):
    """A listed choice, a probability in [0, 1], or a score within the level indices of sent question s."""
    if s["type"] == "choice":
        return isinstance(v, str) and v in [c.get("value") for c in s.get("choices", []) if isinstance(c, dict)]
    return _num(v) and 0 <= v <= (1 if s["type"] == "predicate" else len(s.get("levels", [])) - 1)


def _parse(questions, sent, resp):
    answers = resp.get("answers") if isinstance(resp, dict) else None
    by_name = {a.get("name"): a for a in answers if isinstance(a, dict)} if isinstance(answers, list) else {}
    out = []
    for q, s in zip(questions, sent):
        a = by_name.get(s["name"])
        if a is None:
            out.append(_unknown(q, "missing"))
            continue
        field = _FIELD[q["type"]]
        v = a.get(field)
        # a type other than the question's (e.g. "refusal") or a missing, ill-typed or off-list value is no verdict
        if a.get("type", q["type"]) != q["type"] or not _allowed(s, v):
            out.append(_unknown(q, "refused"))
            continue
        r = {"name": q["name"], "type": q["type"], "status": "ok", field: v}
        if field != "probability":
            r["probabilities"], r["confidence"] = a.get("probabilities"), a.get("confidence")
        out.append(r)
    return out


def _tokens(resp):
    u = resp.get("usage") if isinstance(resp, dict) else None
    u = u if isinstance(u, dict) else {}
    d = u.get("input_tokens_details")
    d = d if isinstance(d, dict) else {}
    n = lambda v: v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0
    return n(u.get("input_tokens")), n(d.get("cached_tokens")), n(d.get("cache_write_tokens"))


def _cost(total, cached, writes):
    fresh = max(total - cached - writes, 0)
    return round((fresh * PRICE_INPUT + cached * PRICE_CACHED + writes * PRICE_WRITE) / 1e6, 8)


def _log(rec):
    path = Path(os.environ.get("MAENG_DECISIONS_LEDGER") or "~/Documents/maeng-harness/decisions/ledger.jsonl").expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:  # the answers still go back; the gap is visible
        print(f"decisions: ledger write failed: {e.strerror}", file=sys.stderr)


def decide(input, questions, pilot, *, model=MODEL, timeout=30.0):
    _validate(questions)
    safe_input, sent = _walk(input), [_walk(q) for q in questions]
    text = safe_input if isinstance(safe_input, str) else json.dumps(safe_input, sort_keys=True, ensure_ascii=False)
    reason, resp, latency = None, None, 0
    if os.environ.get("MAENG_DECISIONS", "").strip().lower() == "off":
        reason = "off"
    elif not (key := _api_key()):
        reason = "no_key"
    else:
        t0 = time.monotonic()
        reason, resp = _call({"model": model, "input": safe_input, "questions": sent}, key, timeout)
        latency = int((time.monotonic() - t0) * 1000)
    results = [_unknown(q, reason) for q in questions] if reason else _parse(questions, sent, resp)
    if reason:
        outcome = reason if reason in ("off", "no_key", "timeout") else "error"
    else:
        n_ok = sum(r["status"] == "ok" for r in results)
        outcome = "ok" if n_ok == len(results) else "partial" if n_ok else "refused"
    total, cached, writes = _tokens(resp)
    _log({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pilot": pilot, "model": model, "n_questions": len(questions),
        "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "input_chars": len(text),
        "outcome": outcome, "latency_ms": latency,
        "input_tokens": total, "cached_tokens": cached, "cache_write_tokens": writes,
        "cost_usd": _cost(total, cached, writes),
        "answers": [{k: r[k] for k in ("name", "status", "reason", "choice", "probability", "score", "confidence") if k in r}
                    for r in results],
    })
    return results
