# Source

- **Author:** Henry.
- **From:** his `chart-style` skill, the Claude app version of 2026-09-18. His henry-skills repo holds a later port of it for Claude Code and Cursor (`plugins/visual-style/skills/chart-style`, 2026-09-19).
- **Copied:** on 2026-10-13. `SKILL.md` is his text. Two things changed: the code block at the bottom (`chartkit.py`) and the font step moved out to files, and a short Toolchain section replaces them; and the two output-path lines (workflow step 4 and the first recipe) use the wording from his own port, which names the project folder for Claude Code and Cursor next to the Claude app's `/mnt/user-data/outputs/`. His voice ("Henry") and the `sdh2` wordmark stay as he wrote them, so a chart made with this skill carries his mark.
- **The toolchain files:**
  - `chartkit.py` is the code block word for word. It is also identical to the copy in his trust404 repo (`scripts/chartkit.py`).
  - `requirements.txt` is new: the skill named matplotlib, numpy and pandas with no versions. The setup run below resolved matplotlib 3.11.2, numpy 2.5.4 and pandas 3.0.6.
  - `setup.sh` is new. It installs into `${ETA_CRAFT_HOME:-$HOME/.eta-craft}/chartkit` (outside the plugin) with a venv, and puts Inter in `~/.fonts` with the skill's own download step when the venv's matplotlib cannot see Inter. After the download it deletes matplotlib's font list, as his port does, because matplotlib does not notice new fonts until the list is rebuilt.
- **Checked on 2026-10-13:** a run of `setup.sh` in an empty home folder (macOS arm64, Python 3.14) took 35 seconds, installed Inter, and made `chartkit.FONT_STACK` start with Inter; a second run took under a second. A test line chart in publish mode rendered to a PNG.
- **Why it is here:** a craft skill: know-how with no eta rule (Testing and quality §8, OPS-A4-16). Henry asked for his chart and diagram skills in eta-craft on 2026-10-13.
