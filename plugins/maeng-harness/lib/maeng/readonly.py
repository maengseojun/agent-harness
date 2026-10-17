"""Closed read-only allowlist for G3: every program is checked against a per-program option allowlist, and any
unknown option makes the invocation NOT read-only (deny by default). Programs whose modes can write, execute or page
(file -C, less -o, more, env <cmd>, rg --pre, ...) are simply absent or have those options absent."""
import re

# spec keys: b = bool short chars, v = value short chars, d = bare -<digits> ok, l = long flags (no value),
# lv = long flags taking a value (`--x=V` or `--x V`), le = long flags with an optional `=V` only, l2 = long flags
# consuming two following tokens.
SPECS = {
    "cat": dict(b="AbeEnstTuv", l={"--number", "--number-nonblank", "--show-all", "--show-ends", "--show-tabs",
                                    "--squeeze-blank", "--show-nonprinting"}),
    "head": dict(b="qvz", v="nc", d=True, l={"--quiet", "--silent", "--verbose", "--zero-terminated"},
                 lv={"--lines", "--bytes"}),
    "tail": dict(b="qvzfFr", v="nc", d=True, l={"--quiet", "--silent", "--verbose", "--zero-terminated", "--follow"},
                 lv={"--lines", "--bytes"}),
    "wc": dict(b="lwcmL", l={"--lines", "--words", "--bytes", "--chars", "--max-line-length"}),
    "stat": dict(b="fLnqrsxlFt", v="c", l={"--dereference", "--file-system", "--terse"}, lv={"--format", "--printf"}),
    "ls": dict(b="1AaBbCcdFfGgHhikLlmnopqRrSsTtuUvwxX@e", l={"--all", "--almost-all", "--classify", "--human-readable",
                                                          "--recursive", "--reverse", "--directory", "--inode",
                                                          "--size", "--dereference", "--group-directories-first"},
               le={"--color", "--colour", "--time-style"}),
    "grep": dict(b="EFGHIPRTUVZabchilnoqrsuvwxyz", v="ABCDdefm", d=True,
                 l={"--ignore-case", "--no-ignore-case", "--invert-match", "--word-regexp", "--line-regexp",
                    "--count", "--files-with-matches", "--files-without-match", "--line-number", "--recursive",
                    "--dereference-recursive", "--no-messages", "--quiet", "--silent", "--only-matching",
                    "--with-filename", "--no-filename", "--text", "--fixed-strings", "--extended-regexp",
                    "--perl-regexp", "--basic-regexp", "--null", "--initial-tab", "--null-data", "--byte-offset"},
                 lv={"--regexp", "--file", "--max-count", "--after-context", "--before-context", "--context",
                     "--include", "--exclude", "--exclude-dir", "--binary-files", "--directories", "--devices"},
                 le={"--color", "--colour"}),
    "rg": dict(b="HhiIlLnNoqsSuUvwxFcPaV", v="ABCegGtTmMjrEdf", d=False,
               l={"--ignore-case", "--smart-case", "--case-sensitive", "--files-with-matches", "--files-without-match",
                  "--count", "--line-number", "--no-line-number", "--only-matching", "--hidden", "--no-ignore",
                  "--word-regexp", "--line-regexp", "--fixed-strings", "--invert-match", "--quiet", "--files",
                  "--heading", "--no-heading", "--with-filename", "--no-filename", "--column", "--follow", "--json",
                  "--multiline", "--pcre2", "--text", "--unrestricted", "--null", "--stats", "--no-messages",
                  "--type-list", "--no-config"},
               lv={"--regexp", "--file", "--glob", "--iglob", "--type", "--type-not", "--max-count", "--max-depth",
                   "--max-filesize", "--threads", "--context", "--after-context", "--before-context", "--replace",
                   "--sort", "--sortr", "--encoding"},
               le={"--color"}),
    "diff": dict(b="abBdeEfHilNnpqrsTtuwyZ", v="CULFIxXW", d=True,
                 l={"--brief", "--ignore-case", "--recursive", "--ignore-all-space", "--ignore-space-change",
                    "--ignore-blank-lines", "--text", "--new-file", "--report-identical-files", "--show-c-function",
                    "--side-by-side", "--minimal", "--strip-trailing-cr", "--no-dereference", "--expand-tabs",
                    "--initial-tab", "--normal", "--ignore-trailing-space", "--unified", "--context"},
                 lv={"--label", "--exclude", "--exclude-from", "--ignore-matching-lines", "--width", "--tabsize"},
                 le={"--color", "--unified", "--context"}),
    "echo": dict(b="neE"),
    "printf": dict(),
    "pwd": dict(b="LP"),
    "which": dict(b="as"),
    "du": dict(b="achHkLmPsxbgKX", v="dB", l={"--summarize", "--human-readable", "--total", "--all", "--apparent-size",
                                              "--bytes", "--dereference", "--one-file-system"},
               lv={"--max-depth", "--block-size", "--exclude"}),
    "df": dict(b="aHhiklPTgmbK", v="t", l={"--human-readable", "--all", "--inodes", "--local", "--portability",
                                           "--total"}, lv={"--type", "--exclude-type"}),
    "tree": dict(b="aCdfFgilnNpqrsuvxDh", v="LPI", l={"--dirsfirst", "--noreport", "--du", "--prune", "--gitignore"},
                 lv={"--charset", "--filelimit", "--sort"}),
    "realpath": dict(b="eEmLPqsz", l={"--canonicalize-existing", "--canonicalize-missing", "--no-symlinks", "--strip",
                                     "--quiet", "--zero"}, lv={"--relative-to", "--relative-base"}),
    "dirname": dict(b="z", l={"--zero"}),
    "basename": dict(b="az", v="s", l={"--multiple", "--zero"}, lv={"--suffix"}),
    "true": dict(), "false": dict(),
    "sort": dict(b="bcCdfghiMmnRrsuVz", v="kS", l={"--ignore-leading-blanks", "--dictionary-order",
                                                                         "--ignore-case", "--general-numeric-sort",
                                                                         "--human-numeric-sort", "--ignore-nonprinting",
                                                                         "--month-sort", "--numeric-sort",
                                                                         "--random-sort", "--reverse",
                                                                         "--version-sort", "--stable", "--unique",
                                                                         "--zero-terminated", "--check"},
                 lv={"--key", "--field-separator", "--buffer-size"}),
    "uniq": dict(b="cdDiuz", v="fsw", l={"--count", "--repeated", "--unique", "--ignore-case", "--zero-terminated"},
                 lv={"--skip-fields", "--skip-chars", "--check-chars"}),
    "cut": dict(b="nsz", v="bcfd", l={"--only-delimited", "--zero-terminated", "--complement"},
                lv={"--bytes", "--characters", "--fields", "--delimiter", "--output-delimiter"}),
    "tr": dict(b="cCdsrt"),
    "env": dict(),
    "date": dict(b="uIRjn", v="dfrvz", l={"--utc", "--universal", "--rfc-email"},
                 lv={"--date", "--file", "--reference"}, le={"--iso-8601", "--rfc-3339"}),
    "jq": dict(b="cCrRsSnejaM", v="fL", l={"--compact-output", "--raw-output", "--slurp", "--null-input", "--exit-status",
                                           "--tab", "--sort-keys", "--color-output", "--monochrome-output",
                                           "--ascii-output", "--raw-input", "--args", "--jsonargs", "--seq",
                                           "--stream", "--join-output", "--raw-output0"},
               lv={"--indent"}, l2={"--arg", "--argjson", "--slurpfile", "--rawfile"}),
    "sha256sum": dict(b="bctw", l={"--binary", "--check", "--text", "--tag", "--zero", "--quiet", "--status", "--warn"}),
    "shasum": dict(b="bctwUBp0", v="a"),
    "md5": dict(b="pqr", v="s"),
    "readlink": dict(b="fenmqsvz"),
}
# test / [ take expression operands that look like options but never write anything
FREE = {"test", "[", "cd", "pushd", "popd"}
PROGS = set(SPECS) | {"find"} | FREE

FIND_FLAG = {"-H", "-L", "-P", "-E", "-X", "-x", "-s", "-d"}
FIND_PRIMARY_BOOL = {"-print", "-print0", "-prune", "-o", "-a", "-and", "-or", "-not", "!", "(", ")", "-depth",
                     "-follow", "-xdev", "-mount", "-empty", "-readable", "-writable", "-executable", "-ls",
                     "-nouser", "-nogroup", "-true", "-false", "-noleaf", "-daystart"}
FIND_PRIMARY_VALUE = {"-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex", "-type",
                      "-xtype", "-maxdepth", "-mindepth", "-size", "-mtime", "-atime", "-ctime", "-mmin", "-amin",
                      "-cmin", "-newer", "-perm", "-user", "-group", "-uid", "-gid", "-links", "-inum", "-lname",
                      "-ilname", "-samefile", "-newermt", "-regextype"}


def _find_ok(args):
    i = 0
    while i < len(args):
        t = args[i]
        if t in FIND_PRIMARY_VALUE:
            if i + 1 >= len(args):
                return False
            i += 2
            continue
        if t in FIND_FLAG or t in FIND_PRIMARY_BOOL:
            i += 1
            continue
        if t.startswith("-") and len(t) > 1 or t.startswith("(") and t != "(":
            return False  # unknown primary (-delete, -exec, -fprint, -newerXY, ...)
        i += 1
    return True


def _opts_ok(args, spec):
    b, v = spec.get("b", ""), spec.get("v", "")
    longs, lv, le, l2 = spec.get("l", ()), spec.get("lv", ()), spec.get("le", ()), spec.get("l2", ())
    i = 0
    while i < len(args):
        t = args[i]
        if t == "--":
            return True
        if t.startswith("--"):
            name, eq, _ = t.partition("=")
            if name in longs and not eq:
                pass
            elif name in le:
                pass
            elif name in lv:
                if not eq:
                    if i + 1 >= len(args):
                        return False
                    i += 1
            elif name in l2 and not eq:
                i += 2
            else:
                return False
        elif t.startswith("-") and len(t) > 1:
            if spec.get("d") and t[1:].isdigit():
                i += 1
                continue
            j = 1
            while j < len(t):
                c = t[j]
                if c in v:
                    if j == len(t) - 1:
                        if i + 1 >= len(args):
                            return False
                        i += 1
                    break
                if c in b or (spec.get("d") and c.isdigit()):
                    j += 1
                    continue
                return False
        i += 1
    return True


def program_readonly(prog, toks):
    """toks[0] is the program; True when its options pass the allowlist (positional operands are read targets)."""
    args = toks[1:]
    if prog in FREE:
        return True
    if prog == "find":
        return _find_ok(args)
    spec = SPECS.get(prog)
    if spec is None:
        return False
    if prog == "env":
        return not args
    if prog == "uniq" and len([t for t in args if not t.startswith("-")]) >= 2:
        return False
    return _opts_ok(args, spec)


# ---- git (read-only subcommands) -------------------------------------------

GIT_SHORT = set("abcdefhilmnpqrstuvwxzACDEFGHIKLMNPRSTUVWXZ0123456789")  # never O (--open-files-in-pager)
GIT_LONG = {
    "--stat", "--shortstat", "--numstat", "--dirstat", "--name-only", "--name-status", "--summary", "--oneline",
    "--abbrev-commit", "--no-abbrev-commit", "--graph", "--decorate", "--no-decorate", "--all", "--branches", "--tags",
    "--remotes", "--follow", "--no-merges", "--merges", "--first-parent", "--reverse", "--patch", "--no-patch",
    "--cached", "--staged", "--no-color", "--ignore-space-change", "--ignore-all-space", "--ignore-blank-lines",
    "--ignore-space-at-eol", "--find-renames", "--find-copies", "--minimal", "--histogram", "--patience", "--raw",
    "--full-index", "--check", "--quiet", "--short", "--long", "--branch", "--porcelain", "--ignored", "--show-current",
    "--verify", "--show-toplevel", "--show-prefix", "--show-cdup", "--git-dir", "--is-inside-work-tree",
    "--is-bare-repository", "--abbrev-ref", "--symbolic-full-name", "--symbolic", "--others", "--exclude-standard",
    "--deleted", "--modified", "--stage", "--full-name", "--full-tree", "--line-number", "--ignore-case",
    "--invert-match", "--word-regexp", "--count", "--files-with-matches", "--files-without-match", "--fixed-strings",
    "--extended-regexp", "--perl-regexp", "--and", "--or", "--not", "--heading", "--break", "--show-function",
    "--function-context", "--untracked", "--no-index", "--always", "--exact-match", "--is-ancestor", "--octopus",
    "--fork-point", "--independent", "--topo-order", "--date-order", "--author-date-order", "--left-right",
    "--cherry-pick", "--cherry-mark", "--boundary", "--children", "--parents", "--numbered", "--summary", "--cc",
    "--no-renames", "--text", "--binary", "--no-textconv", "--no-ext-diff", "--textconv-never", "--dirty", "--contains",
    "--no-contains", "--merged", "--no-merged", "--null", "--nul", "--eol", "--size", "--batch-check", "--batch",
    "--batch-all-objects", "--unordered", "-z", "--end-of-options", "--pickaxe-all", "--pickaxe-regex",
    "--show-signature", "--no-notes", "--relative-date", "--first-parent-only", "--sparse", "--simplify-by-decoration",
    "--ancestry-path", "--remove-empty", "--full-history", "--dense", "--default", "--not-exists", "--exclude-per-directory",
    "--directory", "--no-empty-directory", "--resolve-undo", "--killed", "--unmerged", "--lines", "--word-diff",
    "--color-words", "--color", "--check-attr",
}
GIT_LONG_VALUE = {
    "--pretty", "--format", "--abbrev", "--date", "--author", "--committer", "--grep", "--since", "--until", "--after",
    "--before", "--max-count", "--skip", "--diff-filter", "--unified", "--max-depth", "--color", "--word-diff",
    "--color-words", "--diff-algorithm", "--ignore-submodules", "--untracked-files", "--find-renames",
    "--find-copies", "--stat", "--shortstat", "--numstat", "--dirstat", "--src-prefix", "--dst-prefix",
    "--decorate", "--branches", "--tags", "--remotes", "--glob", "--exclude", "--match", "--contains", "--merged",
    "--no-merged", "--points-at", "--sort", "--relative", "--inter-hunk-context", "--line-prefix", "--since-as-filter",
    "--column", "--pickaxe", "-S", "--lines", "--default", "--prefix", "--max-parents", "--min-parents", "--candidates",
    "--abbrev-commit",
}


def git_options_ok(args):
    """Options of a read-only git subcommand (operands, revisions and paths are not options)."""
    for t in args:
        if t == "--":
            return True
        if t.startswith("--"):
            name = t.partition("=")[0]
            if name not in GIT_LONG and name not in GIT_LONG_VALUE:
                return False
        elif t.startswith("-") and len(t) > 1:
            if t == "-z" or all(c in GIT_SHORT for c in t[1:]):
                continue
            return False
    return True


# ---- gh (read-only) ----------------------------------------------------------

GH_READ_FLAGS = {
    "--json", "-q", "--jq", "-t", "--template", "--web", "-w", "--comments", "-c", "--paginate", "--slurp", "--include",
    "-i", "--silent", "--verbose", "--patch", "--name-only", "--color", "--limit", "-L", "--state", "-s", "--author",
    "--label", "-l", "--assignee", "-a", "--search", "-S", "--base", "-B", "--head", "-H", "--app", "--watch", "--log",
    "--log-failed", "--job", "-j", "--attempt", "--exit-status", "--branch", "-b", "--user", "--event", "-e",
    "--workflow", "--status", "--archived", "--hostname", "--header", "--cache", "--required", "--fail-fast",
    "--interval", "--ref", "--repo", "-R", "--method", "-X", "--mention", "--milestone", "-m", "--draft", "-d",
    "--no-archived", "--source", "--fork", "--language", "--topic", "--visibility", "--order", "--sort", "--yaml", "-y",
    "--exclude-pr", "--created", "--commit", "-r", "--help", "-h", "--version",
}


def gh_options_ok(info):
    return all(f.partition("=")[0] in GH_READ_FLAGS for f in info["flags"])
