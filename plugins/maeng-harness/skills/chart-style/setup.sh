#!/usr/bin/env bash
# Installs the chartkit toolchain of the chart-style skill into ${ETA_CRAFT_HOME:-$HOME/.eta-craft}/chartkit.
# Safe to run again: it refreshes chartkit.py and installs only what is missing.
# Needs network the first time and Python 3.10 or newer.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${ETA_CRAFT_HOME:-$HOME/.eta-craft}/chartkit"
FONTS="$HOME/.fonts"

fail() { echo "setup: $*" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || fail "python3 is needed and was not found"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || fail "Python 3.10 or newer is needed"

mkdir -p "$DEST"
for f in chartkit.py requirements.txt; do
  cp "$SRC/$f" "$DEST/$f"
done
cd "$DEST"

# A Python venv with matplotlib, numpy and pandas.
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt

# Inter for Latin text. Without it chartkit falls back to Helvetica or DejaVu Sans, so a failure here is a warning.
if ! .venv/bin/python -c "import sys; import matplotlib.font_manager as fm; sys.exit(0 if 'Inter' in {f.name for f in fm.fontManager.ttflist} else 1)"; then
  if command -v curl >/dev/null 2>&1 && command -v unzip >/dev/null 2>&1; then
    tmp="$(mktemp -d)"
    if curl -fsSL -o "$tmp/inter.zip" https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip \
      && unzip -o -q "$tmp/inter.zip" -d "$tmp/inter"; then
      mkdir -p "$FONTS"
      cp "$tmp"/inter/extras/ttf/Inter-{Regular,Medium,SemiBold,Bold}.ttf "$FONTS/"
      fc-cache -f >/dev/null 2>&1 || true
      # matplotlib keeps a font list and does not notice new fonts until that list is gone.
      cachedir="$(.venv/bin/python -c 'import matplotlib; print(matplotlib.get_cachedir())')"
      rm -f "$cachedir"/fontlist-*.json
    else
      echo "setup: warning: the Inter download failed; charts will use the fallback font" >&2
    fi
    rm -rf "$tmp"
  else
    echo "setup: warning: curl and unzip are needed to fetch Inter; charts will use the fallback font" >&2
  fi
fi

echo "setup ok: $DEST"
echo "run with: PYTHONPATH=\"$DEST\" \"$DEST/.venv/bin/python\" make_chart.py"
