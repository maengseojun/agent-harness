# Spec/Plan: public README

Goal: the repository is public (2026-11-03); visitors get an English README at the root.

- AC-1: README.md at the repository root describes the two plugins, the work loop, selected skills, install steps, layout and the contribution policy (collaborators only), and every path or command it names exists in this tree.
- AC-2: no other file changes besides README.md and this plan. Check: `python3 -m pytest -q` passes.
