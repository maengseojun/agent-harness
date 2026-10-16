# Minimal Graphify → Archify adapter

This integration's Python standard-library script is not an official converter. It produces only an **architecture draft** from a deliberately selected subgraph. Author workflow/sequence/dataflow/lifecycle JSON separately when ordering or state semantics matter; static call links do not establish those semantics.

Input: `snapshot.json` from graphify-repository and a reviewed selection JSON. Output: `candidate.json` plus `candidate.provenance.json`. The provenance keeps raw selected nodes/edges, original IDs, relation direction and its basis, revision, dirty status, file hashes, source path/line, EXTRACTED/INFERRED/UNVERIFIED status, selection scope, exclusions and omitted counts. Keep both files with the rendered HTML; Archify's closed schema cannot carry all this metadata itself.

```json
{
  "title": "요청과 저장의 관계",
  "question": "어떤 함수가 저장을 호출하는가?",
  "assumptions": ["정적 분석만 사용하며 실제 실행 순서는 측정하지 않았다."],
  "example": "하나의 입력을 받아 저장하는 경로를 따라간다.",
  "check_question": "점선 관계는 실행이 확인됐다는 뜻인가?",
  "answer": "아니다. 추론 또는 미확인 관계이며 원문 검토가 필요하다.",
  "scope": "선택한 두 함수의 관계",
  "excluded": ["동적 호출", "문서와 미디어"],
  "output": "explanation.html",
  "nodes": ["original-node-id-a", "original-node-id-b"],
  "edges": [{"index": 0, "review": {"status": "source-confirmed", "note": "호출 구문과 피호출 정의를 직접 읽음", "sources": [{"path": "src/main.py", "line": 12}]}}]
}
```

Use `review.status: "unverified"` with an honest note for unresolved edges; they render UNVERIFIED even if extraction said EXTRACTED. Source-confirmed does not turn INFERRED into EXTRACTED. The script checks source hashes, indexed paths and line existence, but a human/agent must assess what those lines mean.

Direction: `_src`/`_tgt` win when both exist; partial markers or conflicting review directions fail. For raw AST `edges` without `directed:false`, preserve stored source→target order. For Graphify-built `directed:false` without markers, **require** selected `from`, `to`, and `direction_note` from source review; preserve the original edge too. Never load into an undirected graph and reconstruct arrows from its reordered endpoints. Undirected association requires a separately authored headless representation; this arrow-based adapter cannot faithfully convert it.

Set `SKILL_DIR` to the resolved absolute directory of the installed `interactive-explainer` skill. Keep the current working directory at the intended output folder.

```sh
python3 "$SKILL_DIR/scripts/graphify_to_archify.py" --snapshot /absolute/index/snapshot.json --selection selection.json --repo /absolute/repository --out candidate.json
```

All source hashes must still match. No files are uploaded, no LLM is called, and existing output paths are refused. Unknown source locations remain path-only, never invented lines. Component type `backend` is a neutral renderer placeholder, not an inferred deployment fact: review type, title, tags and geometry before delivery. The fixed commit subtitle and dirty card provide context; detailed sources remain in the sidecar and working-source cards. The adapter deliberately omits Archify `sources` fields, which require immutable repository metadata; adding them later requires verified clean-commit authoring. Keep labels/values consistent with the editable diagram and teaching companion.
