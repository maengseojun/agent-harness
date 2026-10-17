---
name: ai-loop-design
description: Use when an idea for a product, tool or AI-powered system is being shaped - interview or architecture stage, "아이디어 설계", "AI로 뭘 만들지", "AI에게 어떻게 분배", "무엇을 허용/제한", "검증 기준", "문제 분해", "다른 도메인에서 빌려오기", design an agent loop, decide what the model vs code vs human owns. A checklist that decomposes the problem, borrows tools from other domains by structure, splits roles between model, code and human, puts constraints in code and fixes verification criteria before generation. Not for implementing an agreed plan (execute-code-brief) or for pitch/marketing copy.
---

# ai-loop-design (AI 루프 설계 점검)

Principle: **do not ask the model for an answer; ask it for a loop. The answer is what survives the loop.** The human owns the problem, its structure and the criteria; the model explores, generates and attacks; code computes; independent evidence judges; the human makes the final choice.

Run the steps in order and write the result of each into the interview notes or the parent Spec. Ask the user only where a step needs their judgment (marked **user**). Keep it proportional: a small idea gets one line per step.

## Steps

1. **Decompose (first principles).** Break the problem down until each part is a plain fact or a single decision. Question every requirement ("who asked for this, and why?") and delete what is not needed; decisions the user already settled stay settled. Find the one part that, if solved, makes the rest easy. **user** confirms the core.
2. **Restate the structure.** Describe the core with verbs, not domain nouns: "an irreversible, expensive decision under uncertain inputs; we want the failure conditions before acting", not "opening a cafe". **user** confirms this is the essence.
3. **Is this AI-only value?** Check at least one: many counterfactuals run in parallel; tireless self-attack; links between distant domains; turning expensive, irreversible trial and error into cheap, reversible experiments. If the idea is only "do a human task faster", say so plainly; it is a weak differentiator.
4. **Borrow by structure, not by solution.** Find fields that already solved the same structure (stress testing, yield maps, red teaming, queueing, actuarial, clinical trials, simulators...) and what each lends: a **metric**, a **visualization**, a **procedure** or a **formula**. Research through `aside-research` (or `aside-collect` for gathering only); in the eta world follow those skills' eta world rules. For every borrowed tool record: the assumptions it rests on, the conditions where it breaks, the most common mistake practitioners make, and a 1:1 mapping table (theirs -> ours) with the places the mapping fails. Learn "when it is wrong", not "how to master it".
5. **Success hypothesis.** One sentence, written now, before anything is built: who, what changes in their decision, how we would notice. Measuring it needs a finished product and real users; that is recommended follow-up, not part of this checklist.
6. **Assign roles.**

   | Role | Owns | Must not |
   |---|---|---|
   | Model (generator) | alternatives, as structured patches (e.g. JSON) | produce numbers, judge itself |
   | Model or rules (adversary) | conditions that break the design | share the generator's blind spots; prefer a different model or a rule-based fuzzer |
   | Code (oracle) | every calculation and the pass/fail judgment, deterministic | be probabilistic |
   | Verifier | audit against fixed evidence only | share the author's context |
   | Human | problem choice, accepted assumptions, final decision | micro-steer the loop |

7. **Constraints in code, not in prompts.** The model must not read or edit what it would want to win against: criteria, answer keys, tests, oracle code, result numbers. Enforce with paths, permissions or hooks (forbidden paths), and fix the input/output contract (SPEC, schemas) before the first line of code so lanes can run in parallel.
8. **Fix verification criteria before generation.** Criteria come from someone other than the generator (the human, a textbook, another model) and evidence is external (raw data, a real URL, reproducible tests); a model's "it passed" is not evidence.

   | Layer | Question | Example |
   |---|---|---|
   | L0 contract | Is the shape right? | schemas, SPEC fixed upfront |
   | L1 correctness | Is the borrowed formula implemented right? | known-answer tests from an independent source (textbook worked examples), limit cases (zero arrivals -> zero queue) |
   | L2 invariants | Does it produce nonsense? | monotonicity (higher rent never improves survival), impossible states flagged |
   | L3 reality | Does it match the world? | backtest on real data |
   | L4 sensitivity | Which assumption flips the conclusion? | perturb one assumption at a time; report the flip points |

   Known-answer tests (L1) are what let a non-expert trust borrowed domain math: you can check the textbook answer without deriving the formula.
9. **After a verified result exists,** **user** is asked: "이 결과를 HTML로 만들어볼까요?" Do not build a prototype before the loop has produced a verified result.

## Watch for

- **False precision.** Ten thousand simulated futures are only as good as the oracle's assumptions; surface the assumptions that change the conclusion (L4) rather than the volume of runs.
- **Goodhart.** Any criterion the model can see becomes its target.
- **Unchecked borrowing.** In a domain you do not know, a wrong answer from the model looks right; without L1 you will not notice.

## Output

A short design note with: the core (1), the structure sentence (2), the AI-only reason or the honest "weak" (3), the borrowed tools with assumptions, breaking conditions and mapping (4), the success hypothesis (5), the role table (6), the code-level constraints (7) and the L0-L4 criteria (8). In the personal world this goes into the parent Spec; in the eta world follow eta's own rules for where design notes live.
