"""Quote-aware command splitting for the gates. Raises ParseError when unsure."""
import os
import re

OPERATORS = ("&&", "||", ";", "|", "&", "\n")
WRAPPER_PREFIX = {"env", "command", "time", "nohup", "sudo", "exec", "nice", "builtin"}
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


class ParseError(Exception):
    pass


class Segment:
    def __init__(self, tokens, op_after="", redirects=None):
        self.tokens = tokens
        self.op_after = op_after
        self.redirects = redirects or []

    def __repr__(self):
        return f"Segment({self.tokens!r}, {self.op_after!r})"


def _find_close(text, i, opener, closer):
    """Index just after the matching closer, honoring quotes and nesting."""
    depth, quote = 1, None
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 1
            elif c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c == "\\":
            i += 1
        elif opener != closer and c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ParseError("unterminated substitution")


def split_segments(command, _depth=0):
    """Split into Segments; substitutions are parsed recursively as extra segments."""
    if _depth > 5:
        raise ParseError("nesting too deep")
    segments, extra = [], []
    tokens, redirects, cur, have = [], [], [], False
    heredocs = []
    i, n = 0, len(command)

    def flush_word():
        nonlocal cur, have
        if have:
            tokens.append("".join(cur))
        cur, have = [], False

    def end_segment(op):
        nonlocal tokens, redirects
        flush_word()
        if tokens or redirects:
            segments.append(Segment(tokens, op, redirects))
        tokens, redirects = [], []

    def substitution(start, opener, closer):
        end = _find_close(command, start, opener, closer)
        inner = command[start:end - 1]
        extra.extend(split_segments(inner, _depth + 1))
        return end

    while i < n:
        c = command[i]
        if c == "\\":
            if i + 1 < n:
                cur.append(command[i + 1]); have = True
            i += 2
        elif c == "'":
            j = command.find("'", i + 1)
            if j < 0:
                raise ParseError("unterminated quote")
            cur.append(command[i + 1:j]); have = True
            i = j + 1
        elif c == '"':
            have = True
            i += 1
            while True:
                if i >= n:
                    raise ParseError("unterminated quote")
                d = command[i]
                if d == '"':
                    i += 1
                    break
                if d == "\\" and i + 1 < n:
                    cur.append(command[i + 1]); i += 2
                elif d == "$" and command[i + 1:i + 2] == "(":
                    end = substitution(i + 2, "(", ")")
                    cur.append(command[i:end]); i = end
                elif d == "`":
                    end = substitution(i + 1, "`", "`")
                    cur.append(command[i:end]); i = end
                else:
                    cur.append(d); i += 1
        elif c == "$" and command[i + 1:i + 2] == "(":
            end = substitution(i + 2, "(", ")")
            cur.append(command[i:end]); have = True
            i = end
        elif c == "`":
            end = substitution(i + 1, "`", "`")
            cur.append(command[i:end]); have = True
            i = end
        elif command.startswith("<<", i) and not command.startswith("<<<", i):
            m = re.match(r"<<-?\s*(['\"]?)([A-Za-z0-9_]+)\1", command[i:])
            if not m:
                raise ParseError("odd heredoc")
            heredocs.append(m.group(2))
            flush_word()
            i += m.end()
        elif c in "<>":
            if have and "".join(cur).isdigit():
                cur, have = [], False  # fd number, e.g. 2>&1
            flush_word()
            j = i
            while j < n and command[j] in "<>&":
                j += 1
            op = command[i:j]
            while j < n and command[j] in " \t":
                j += 1
            k = j
            while k < n and command[k] not in " \t\n;&|()<>":
                k += 1
            target = command[j:k].strip("'\"")
            if ">" in op and k > j and not (op.endswith("&") and (target.isdigit() or target == "-")):
                redirects.append(target)
            i = k
        elif c in " \t":
            flush_word()
            i += 1
        elif c == "\n":
            end_segment("\n")
            i += 1
            while heredocs:
                delim = heredocs.pop(0)
                while i < n:
                    j = command.find("\n", i)
                    line = command[i:] if j < 0 else command[i:j]
                    i = n if j < 0 else j + 1
                    if line.strip() == delim:
                        break
        elif command.startswith(("&&", "||"), i):
            end_segment(command[i:i + 2]); i += 2
        elif c in ";|&":
            end_segment(c); i += 1
        elif c in "()":
            end_segment(""); i += 1
        else:
            cur.append(c); have = True
            i += 1
    end_segment("")
    return segments + extra


def strip_prefix(tokens):
    """Drop env assignments and benign wrappers (env, sudo, time...)."""
    toks = list(tokens)
    while toks:
        if ENV_ASSIGN.match(toks[0]) or toks[0] in WRAPPER_PREFIX:
            if toks[0] == "env":
                toks.pop(0)
                while toks and (toks[0].startswith("-") or ENV_ASSIGN.match(toks[0])):
                    toks.pop(0)
                continue
            toks.pop(0)
            continue
        break
    return toks


def program(tokens):
    toks = strip_prefix(tokens)
    return (os.path.basename(toks[0]), toks) if toks else ("", [])


SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
RISKY = re.compile(r"\bpush\b|\bmerge\b|\bpr\s+create\b|\bgh\s+(?:release|api|repo|workflow)\b|\bupdate-branch\b|\bmaeng-ship\b")


def uses_wrapper(segments):
    """True when a segment is `sh -c ...` or `eval ...`; returns the payload text."""
    for seg in segments:
        prog, toks = program(seg.tokens)
        if prog in SHELLS and any(re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", t) for t in toks[1:4]):
            return " ".join(toks)
        if prog == "eval":
            return " ".join(toks)
    return None


STRUCTURE_WORDS = {"if", "then", "elif", "else", "fi", "while", "until", "for", "do", "done", "case", "esac",
                   "select", "function", "{", "}", "!"}
ROUTE = re.compile(r"\bpush\b|\bmerge\b|\bpr\s+create\b|\bgh\s+(?:release|api|repo|workflow|pr)\b|"
                   r"\bupdate-branch\b|\bmaeng-ship\b|\bgit\b.*\s(?:-C|--git-dir|--work-tree)\b|\bgit\s+(?:-c\b)")


def has_control_structure(command, segments):
    """True for if/while/for/case/function bodies, `{ ...; }` groups and `( )` subshells (not evaluated)."""
    for seg in segments:
        toks = list(seg.tokens)
        while toks and ENV_ASSIGN.match(toks[0]):
            toks.pop(0)
        if toks and (toks[0] in STRUCTURE_WORDS or toks[0].endswith("()")):
            return True
    quote, i, n = None, 0, len(command)
    while i < n:
        c = command[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 1
            elif c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c == "\\":
            i += 1
        elif c == "(" and command[i - 1:i] not in ("$", "<", ">"):
            return True
        i += 1
    return False
