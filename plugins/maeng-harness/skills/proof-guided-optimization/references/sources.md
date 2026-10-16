# Source basis and limits

The public source set is pinned to OpenAI's `math` repository revision
[`adc7f1241b42e322a6451854ab7e4b4c146bf78a`](https://github.com/openai/math/tree/adc7f1241b42e322a6451854ab7e4b4c146bf78a).
The page numbers below are PDF page numbers. A matching source ID and page range
is the locator; follow the fixed-revision PDF link to inspect it.

## Evidence labels

- **O — observed:** a reasoning summary records a failure, transition, or proposed
  proof structure, or a manuscript states a proof step. This does not certify the
  mathematical claim in that manuscript.
- **S — synthesis:** a conditional workflow proposal derived from those observations.
  It is not a proved meta-theorem or a behaviorally validated method.
- **E — engineering transfer:** a proposed way to ask questions in DeFi, databases,
  or algorithms. No implementation, benchmark, or live transaction in this source
  work establishes improved performance or safety.

The synthesis compares ten selected result families using prior dossier analysis
and targeted original-page checks. It did not freshly reread all 856 pages of that
prior analysis. Cited pages mix dossier-supported locations and targeted checks;
do not describe every cited page as independently reread. The family IDs count
distinct result groups, not independent experiments, probabilities, or success
rates. The public summaries do not expose the internal model or its full method.

## Coverage history and verification boundary

The initial 2026-10-07/08 skill inspected R102 pp.1–12, R087 pp.1–10,
and R159 pp.1–6, plus the repository and Lean verification instructions.
The expanded dossier analysis covers 11 direct manuscripts (654 PDF pages) and
10 public summaries (202 pages), grouped in 10 families. Another 11 companion
manuscripts (336 pages) were mapped only, and 700 catalogue-only manuscripts were
not used as supporting evidence. Later targeted checks do not retroactively change
what the initial version read. No Lean/Comparator challenge was run.

The [repository README](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/README.md)
describes generated manuscripts and differing verification stages; inspect the
specific result's current status before importing its theorem. The
[Lean guidance](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/lean/README.md)
and [Comparator instructions](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/lean/ComparatorChallenges/README.md)
were read, not executed. Refresh and record the revision before relying on later
source corrections. Earlier one-repair and stop-at-missing-theorem restrictions
were unsupported and were removed; the corpus prescribes no fixed search count.

## Fixed source index

| Family | Reasoning summary | Manuscript(s) |
| --- | --- | --- |
| F007 | [R-007 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/reasoning_traces/ordinary-two-point-correlations.pdf) | [P-007-01 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/preprints/Ordinary-two-point-correlations-of-multiplicative-functions-September-24-2026/final.pdf) |
| F017 | [R-017 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/reasoning_traces/irrationality-exponent-of-pi.pdf) | [P-017-01 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/preprints/The-irrationality-exponent-of-pi-is-2-September-24-2026/paper.pdf) |
| F087 | [R-087 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/reasoning_traces/symmetric-and-general-mahler-conjectures.pdf) | [P-087-01 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/preprints/The-symmetric-Mahler-conjecture-and-its-equality-cases-September-22-2026/paper.pdf); [P-087-02 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/preprints/The-Mahler-Conjecture-for-General-Convex-Bodies-September-22-2026/paper.pdf) |
| F102 | [R-102 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/reasoning_traces/basic-semidefinite-threshold-np-hardness.pdf) | [P-102-01 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/preprints/The-Unique-Games-Theorem-September-23-2026/paper.pdf) |
| F159 | [R-159 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/reasoning_traces/quasipolynomial-arithmetic-progressions.pdf) | [P-159-01 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/preprints/Quasipolynomial-Bounds-for-Arithmetic-Progressions-September-23-2026/paper.pdf) |
| F197 | [R-197 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/reasoning_traces/kaplansky-direct-finiteness-characteristic-two.pdf) | [P-197-02 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/preprints/A-Counterexample-to-Kaplanskys-Direct-Finiteness-Conjecture-in-Characteristic-Two-September-23-2026/paper.pdf) |
| F221 | [R-221 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/reasoning_traces/mezard-parisi-formula.pdf) | [P-221-01 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/preprints/The-Mezard-Parisi-formula-for-diluted-spin-glasses-September-23-2026/paper.pdf) |
| F271 | [R-271 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/reasoning_traces/spontaneous-magnetization-quantum-heisenberg-ferromagnet.pdf) | [P-271-04 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/preprints/Spontaneous-magnetization-in-the-quantum-Heisenberg-ferromagnet-September-24-2026/paper.pdf) |
| F287 | [R-287 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/reasoning_traces/free-group-factor-isomorphism.pdf) | [P-287-01 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/preprints/An-isomorphism-of-the-free-group-factors-September-23-2026/An-isomorphism-of-the-free-group-factors-September-23-2026.pdf) |
| F362 | [R-362 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/reasoning_traces/relativistic-vlasov-maxwell.pdf) | [P-362-01 PDF](https://github.com/openai/math/blob/adc7f1241b42e322a6451854ab7e4b4c146bf78a/preprints/Global-classical-solutions-of-the-three-dimensional-relativistic-Vlasov-Maxwell-system-September-23-2026/paper.pdf) |

## Methodology locators

These are the source locations used for the **O** observations that informed each
conditional **S** rule. Read the indicated pages before importing a particular
result into a proof or implementation.

| Rule | O locators (source ID and PDF pages) |
| --- | --- |
| G01 — target and quantifiers | P-007-01 pp. 3–4; P-017-01 pp. 18–19; P-102-01 pp. 37–39; P-221-01 p. 4; P-271-04 pp. 21–22 |
| G02 — smallest unresolved connection | R-017 p. 6; P-017-01 pp. 12–18; R-087 p. 2; R-159 p. 24; P-159-01 pp. 76–80; R-362 pp. 2, 5; P-362-01 pp. 29–33 |
| G03 — return map across representations | P-102-01 pp. 19–21, 35; P-159-01 pp. 140–145; P-197-02 pp. 12–14; P-362-01 pp. 45–47 |
| G04 — composed loss and choice order | P-017-01 p. 18; P-087-02 pp. 34–36; P-102-01 p. 28; P-159-01 pp. 77–80, 195; P-287-01 pp. 18–19 |
| G05 — falsify the weakest link | R-017 pp. 1, 6; R-087 p. 38; R-197 p. 19; P-197-02 p. 15; R-362 p. 2 |
| G06 — existence, procedure, cost, execution | P-017-01 pp. 17–19; P-102-01 pp. 37–39; P-197-02 p. 1, pp. 22–24; P-287-01 pp. 18–19 |
| B01 — repeated progress and resources | P-102-01 pp. 13–17; P-159-01 pp. 77–80, 195; P-287-01 pp. 18–19 |
| B02 — cancellation and residual cost | P-007-01 p. 76; P-221-01 pp. 10–11, 28; P-362-01 pp. 24–29; P-087-02 pp. 34–36 |
| B03 — law and information transfer | P-102-01 pp. 26–28, 35; P-159-01 pp. 140–145; P-221-01 pp. 22–32; P-271-04 pp. 21–22 |
| B04 — matching bounds and certificates | P-017-01 pp. 12–18; R-087 p. 2; P-087-02 pp. 34–36, 68–70; P-197-02 pp. 12–13 |
| B05 — limits and closure | P-087-01 pp. 18–22; P-221-01 p. 32; P-271-04 pp. 22–24, 45–52; P-287-01 pp. 18–19; P-362-01 pp. 5–7, 29–33, 40–47 |
| B06 — a counterexample in the target class | R-197 p. 1, pp. 19–21; P-197-02 p. 1, pp. 12–14, 25–26 |

The rule names G01–G06 and B01–B06 are stable cross-references, not a checklist.
The source set is selected and correlated; family counts do not estimate the
chance that a rule will work.

## R-087 source erratum

Quarantine the R-087 dossier row claiming that PDF pp. 9–18 contain mode/cusp,
Brouncker/Stirling, Taylor/Jensen, Padé, cyclotomic logarithm, and Liouville
material. That attribution is erroneous and overlaps R-017 material. Do not cite
that row as an R-087 observation. The phrase “model upper bound” for
`p^(1/n) >= e^(-1/2) + o(1)` also reverses the inequality direction. For R-087
use only its verified source locations when needed, including pp. 2 and 38; the
P-087-02 pp. 34–36 figures `1.8` and `1.94` are distinct costs in the same
manuscript, not a version comparison. The original dossier remains an input
record; this skill does not amend it.
