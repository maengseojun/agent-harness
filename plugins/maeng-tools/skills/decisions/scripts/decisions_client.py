#!/usr/bin/env python3
"""OpenAI Decisions API client for the trial week (MAE-306). Stdlib only.

decide(input, questions, pilot) -> one dict per question, in question order:
  {"name", "type", "status": "ok"|"unknown", ...}
An ok answer carries the fields of its type (choice+probabilities+confidence,
probability, or score+probabilities+confidence). An unknown answer carries
"reason": refused | missing | http_<code> | timeout | error | off | no_key
and never a verdict field; "refused" includes an off-list choice or a value out of range.
"disagree" appears only with the model "both". Nothing about the API or the network raises;
invalid questions raise ValueError.

No request is sent when MAENG_DECISIONS=off.

MAENG_DECISIONS_MODEL or model= picks the engine. The default is gpt-6-luna alone. "both" asks
gpt-6-luna and Jev at once: a choice both give is the answer, a choice they differ on is unknown with reason "disagree",
so it goes to the researcher re-check; a probability or score is their mean; if only one engine
answers, its answer stands. A jev-* model goes through the school's BAZE gateway with the keychain
item baze-api-key, in batches of 32 questions, and its answers are turned into the OpenAI shape,
so callers see no difference. Each engine writes its own ledger line.
Every call appends one line to the ledger (MAENG_DECISIONS_LEDGER, default
~/Documents/maeng-harness/decisions/ledger.jsonl): the input is stored as a
sha256 and a character count of the REDACTED text, never the text; the key is
never stored or printed. latency_ms and token counts are 0 when no request
was sent (outcome off, no_key).
"""
import concurrent.futures
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
LUNA, JEV = "gpt-6-luna", "jev-1.14.0"
MODEL = LUNA  # the school adds about 5 credits of masking to every BAZE request (MAE-319)
BAZE_URL = "https://api.baze.co/v1/gateway/decisions/"
JEV_BATCH = 32  # the gateway's limit per request
PRICE_JEV = 0.042
# USD per 1M input tokens; output is not charged. Cached and cache-write
# tokens are included in input_tokens.
PRICE_INPUT, PRICE_CACHED, PRICE_WRITE = 0.10, 0.01, 0.125
# The field each question type must answer with, else the answer is not a verdict.
_FIELD = {"choice": "choice", "predicate": "probability", "score": "score"}

_R = "[REDACTED]"
_PEM = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?:[A-Za-z0-9+/=\s\\\"',-]*?-----END [A-Z ]*PRIVATE KEY-----"  # a whole block, or
                  r"|(?:\r?\n[+\- ]?[ \t]*[A-Za-z0-9+/=]{16,}[ \t]*(?=\r?\n|\Z))*)", re.S)  # only its base64 lines
_URL_CRED = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://)[^/\s]*@")
_SECRET_NAME = r"[\w.-]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PASSPHRASE|PWD|WEBHOOK|[_-]PASS(?![A-Z]))[\w.-]*"  # not "pass=True"
# after a name: its closing quote or bracket, escaped or not, then the operator
_ASSIGN = r"\\?[\"']?\]?[ \t]*(?::=|=>|==|:|=)[ \t]*"
# a triple-quoted string, else the rest of the line: quotes end too early ("a\"b", "a" "b", "a" + "b")
_VALUE = r"\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|[^\r\n]+"
_AUTH = re.compile(rf"(\bAuthorization{_ASSIGN})(?![ \t=>]|\[REDACTED\])({_VALUE})", re.I)
_BEARER = re.compile(r"(\bBearer\s+)[A-Za-z0-9._~+/=-]{8,}", re.I)
_KV = re.compile(rf"(\b{_SECRET_NAME}{_ASSIGN})(?![ \t=>]|\[REDACTED\])({_VALUE})", re.I)
_FLAG = re.compile(r"(--?[\w-]*(?:key|token|secret|password|passwd)[\w-]*[ \t]+)(?!\[REDACTED\])(\"[^\r\n]*\"|'[^\r\n]*'|\S+)", re.I)
# A secret key with its value on the following lines, in a file or a diff: a YAML block ("key: |-" and its
# indented lines), a bracketed value ("key = {" up to its closing line) or one indented value alone ("key:" or
# "key = \", then a quoted or opaque value). A wider next-line form would swallow code such as
# "for t in tokens:" and its body. Indentation is a diff marker plus space, or two spaces: a one-space context
# line of a diff is not indented.
_INDENT = r"(?:[+\- ][ \t]+|[ \t]{2,})"
_NEXT_LINES = re.compile(
    rf"(\b{_SECRET_NAME}{_ASSIGN})"
    rf"(?:[|>][+-]?[0-9]?[ \t]*\r?\n(?:{_INDENT}\S[^\r\n]*(?:\r?\n|\Z))+"
    rf"|[(\[{{][ \t]*\r?\n(?:(?![+\- ]?[ \t]*[)\]}}]){_INDENT}\S[^\r\n]*(?:\r?\n|\Z))+"
    rf"|\\?[ \t]*\r?\n{_INDENT}(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[A-Za-z0-9+/=_.~-]{{16,}}),?[ \t]*(?:\r?\n|\Z))", re.I)
_TOKEN = re.compile(
    r"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_-]{8,}|[sr]k_(?:live|test)_[A-Za-z0-9]{8,}|gh[oprsu]_[A-Za-z0-9]{8,}"
    r"|github_pat_[A-Za-z0-9_]{8,}|xox[bpa]-[A-Za-z0-9-]{8,}|xapp-[A-Za-z0-9-]{8,}|glpat-[A-Za-z0-9_-]{8,}"
    r"|lin_api_[A-Za-z0-9]{8,}|ntn_[A-Za-z0-9]{8,}|npm_[A-Za-z0-9]{8,}|AIza[0-9A-Za-z_-]{16,}|AKIA[0-9A-Z]{16}"
    r"|hooks\.slack\.com/services/\S+|eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]+)")


def redact(text, by_name=True):
    """Replace secrets with [REDACTED]. Over-redacts rather than leaks (a prose
    "key: value" or "Bearer <word>" is also replaced); idempotent. by_name=False keeps only
    what is recognized by its format: public pages name tokens without holding any, and
    masking "max_tokens=1" would make a true and a false claim identical."""
    text = _PEM.sub(_R, text)
    text = _URL_CRED.sub(lambda m: m.group(1) + _R + "@", text)
    text = _BEARER.sub(lambda m: m.group(1) + _R, text)
    if by_name:
        text = _AUTH.sub(lambda m: m.group(1) + _R, text)
        text = _NEXT_LINES.sub(lambda m: m.group(1) + _R + "\n", text)
        text = _KV.sub(lambda m: m.group(1) + _R, text)
        text = _FLAG.sub(lambda m: m.group(1) + _R, text)
    return _TOKEN.sub(_R, text)


def _walk(x, by_name):
    if isinstance(x, str):
        return redact(x, by_name)
    if isinstance(x, list):
        return [_walk(i, by_name) for i in x]
    if isinstance(x, dict):
        return {k: _walk(v, by_name) for k, v in x.items()}
    return x


def _keychain_key(service="openai-api-key"):
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", service, "-w"],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def _api_key(jev=False):
    return _keychain_key("baze-api-key") if jev else os.environ.get("OPENAI_API_KEY", "").strip() or _keychain_key()


def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _call(body, key, timeout, url=URL):
    """-> (reason or None, response). Every failure becomes a reason."""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        return None, _post(url, body, headers, timeout)
    except urllib.error.HTTPError as e:
        return f"http_{e.code}", None
    except (socket.timeout, TimeoutError):
        return "timeout", None
    except urllib.error.URLError as e:
        return ("timeout" if isinstance(e.reason, (socket.timeout, TimeoutError)) else "error"), None
    except Exception:
        return "error", None


def _jev_question(q):
    out = {"instructions": q["instructions"]}
    if q["type"] == "predicate":
        return {**out, "type": "noul"}
    if q["type"] == "choice":
        return {**out, "type": "choice", "criteria": {c["value"]: c.get("description", "") for c in q["choices"]}}
    levels = [f"{v['label']}: {v['description']}" if v.get("description") else v["label"] for v in q["levels"]]
    return {**out, "type": "score", "criteria": levels}


def _from_jev(q, a):
    """One Jev answer in the OpenAI shape, so _parse judges both engines alike."""
    if not isinstance(a, dict):
        return None
    name, t = q["name"], q["type"]
    if a.get("type") != ("noul" if t == "predicate" else t):
        return {"name": name, "type": "refusal"}
    if t == "predicate":
        return {"name": name, "type": t, "probability": a.get("noul")}
    ps = a.get("probabilities")
    ps = ps if isinstance(ps, dict) else {}
    if t == "score":  # Jev keys levels by index as a string
        levels = {str(i): v["label"] for i, v in enumerate(q["levels"])}
        ps = [{"value": int(k), "label": levels[k], "probability": v} for k, v in ps.items() if k in levels]
    else:
        ps = [{"value": k, "probability": v} for k, v in ps.items()]
    return {**a, "name": name, "probabilities": ps}


def _call_jev(model, state, sent, key, timeout):  # state is text: Jev cannot read OpenAI message parts
    """-> (reason or None, response in the OpenAI shape).
    shortcut: one failed batch makes the whole call unknown, retry per batch if that proves common."""
    answers, tokens = [], 0
    for i in range(0, len(sent), JEV_BATCH):
        part = sent[i:i + JEV_BATCH]
        body = {"model": model, "state": state, "questions": {q["name"]: _jev_question(q) for q in part}}
        reason, resp = _call(body, key, timeout, BAZE_URL)
        if reason:
            return reason, {"usage": {"input_tokens": tokens}}
        tokens += _tokens(resp)[0]
        got = resp.get("answers") if isinstance(resp, dict) else None
        got = got if isinstance(got, dict) else {}
        answers += [a for a in (_from_jev(q, got.get(q["name"])) for q in part) if a]
    return None, {"answers": answers, "usage": {"input_tokens": tokens}}


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
    return isinstance(v, int) and not isinstance(v, bool) or isinstance(v, float) and math.isfinite(v)


def _share(v):
    return _num(v) and 0 <= v <= 1


def _allowed(s, v):
    """A listed choice, a probability in [0, 1], or a score within the level indices of sent question s."""
    if s["type"] == "choice":
        return isinstance(v, str) and v in [c.get("value") for c in s.get("choices", []) if isinstance(c, dict)]
    return _share(v) if s["type"] == "predicate" else _num(v) and 0 <= v <= len(s.get("levels", [])) - 1


def _parse(questions, sent, resp):
    answers = resp.get("answers") if isinstance(resp, dict) else None
    by_name = {a["name"]: a for a in answers if isinstance(a, dict) and isinstance(a.get("name"), str)} \
        if isinstance(answers, list) else {}
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
            ps, c = a.get("probabilities"), a.get("confidence")  # extras of a valid answer: dropped if malformed
            r["probabilities"] = [p for p in ps if isinstance(p, dict) and _share(p.get("probability"))] \
                if isinstance(ps, list) else []
            r["confidence"] = c if _share(c) else None
        out.append(r)
    return out


def _tokens(resp):
    u = resp.get("usage") if isinstance(resp, dict) else None
    u = u if isinstance(u, dict) else {}
    d = u.get("input_tokens_details")
    d = d if isinstance(d, dict) else {}
    n = lambda v: v if isinstance(v, int) and not isinstance(v, bool) and 0 <= v < 2 ** 53 else 0
    return n(u.get("input_tokens")), n(d.get("cached_tokens")), n(d.get("cache_write_tokens"))


def _cost(total, cached, writes, price=PRICE_INPUT):
    fresh = max(total - cached - writes, 0)
    return round((fresh * price + cached * PRICE_CACHED + writes * PRICE_WRITE) / 1e6, 8)


def _log(rec):
    path = Path(os.environ.get("MAENG_DECISIONS_LEDGER") or "~/Documents/maeng-harness/decisions/ledger.jsonl").expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")  # ASCII: a lone surrogate in an answer cannot fail the write
    except OSError as e:  # the answers still go back; the gap is visible
        print(f"decisions: ledger write failed: {e.strerror}", file=sys.stderr)


def _merge(a, b):
    if a["status"] != "ok" or b["status"] != "ok":
        return b if b["status"] == "ok" else a
    if a["type"] == "choice":
        if a["choice"] == b["choice"]:
            return a
        return {"name": a["name"], "type": a["type"], "status": "unknown", "reason": "disagree"}
    field = "probability" if a["type"] == "predicate" else "score"
    return {**a, field: (a[field] + b[field]) / 2}


def decide(input, questions, pilot, *, model=None, timeout=30.0, redact_by_name=True):
    _validate(questions)
    model = model or os.environ.get("MAENG_DECISIONS_MODEL", "").strip() or MODEL
    if model == "both":
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            runs = [pool.submit(decide, input, questions, pilot, model=m, timeout=timeout, redact_by_name=redact_by_name)
                    for m in (LUNA, JEV)]
        return [_merge(a, b) for a, b in zip(runs[0].result(), runs[1].result())]
    jev = model.startswith("jev-")
    safe_input, sent = _walk(input, redact_by_name), [_walk(q, redact_by_name) for q in questions]
    text = safe_input if isinstance(safe_input, str) else json.dumps(safe_input, sort_keys=True, ensure_ascii=False)
    reason, resp, latency = None, None, 0
    if os.environ.get("MAENG_DECISIONS", "").strip().lower() == "off":
        reason = "off"
    elif not (key := _api_key(jev)):
        reason = "no_key"
    else:
        t0 = time.monotonic()
        reason, resp = _call_jev(model, text, sent, key, timeout) if jev else \
            _call({"model": model, "input": safe_input, "questions": sent}, key, timeout)
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
        "input_sha256": hashlib.sha256(text.encode("utf-8", "replace")).hexdigest(), "input_chars": len(text),
        "outcome": outcome, "latency_ms": latency,
        "input_tokens": total, "cached_tokens": cached, "cache_write_tokens": writes,
        "cost_usd": _cost(total, cached, writes, PRICE_JEV if jev else PRICE_INPUT),
        "answers": [{k: r[k] for k in ("name", "status", "reason", "choice", "probability", "score", "confidence") if k in r}
                    for r in results],
    })
    return results
