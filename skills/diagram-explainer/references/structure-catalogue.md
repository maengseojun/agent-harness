# Structure catalogue — diagrams.net / draw.io

## Research coverage and provenance

Reviewed on 2026-10-10. These are original, editable Korean starting layouts informed by public template catalogues, not copies of third-party boards or a claim of model retraining.

- [Blocks & Arrows diagrams](https://blocksandarrows.com/diagrams): sampled first listings across eight working categories, roughly 90 titles. The all catalogue reported 447 pages; not all pages or detailed boards were read. Its database category returned 404. Category names can misclassify diagrams, so inspect actual relationships.
- [Whimsical templates](https://whimsical.com/templates): read all seven listing pages, 82 template cards. Detailed visual inspection: [UML activity diagram](https://whimsical.com/templates/uml-activity-diagram), plus the [sequence template](https://whimsical.com/templates/uml-sequence-diagram) page; not 82 full boards.
- Detailed boundary example: [API gateway/auth architecture](https://blocksandarrows.com/diagrams/band/api-gateway-auth-microservices-architecture-diagram-ywr7). It shows containment plus data paths; the drawing is not proof of security or deployment.
- Aside tab discovery worked, but opening the source failed with Transport closed. Source reading continued in the Codex browser. Do not turn a failed browser into an assertion that a site has no examples.

## Role of this catalogue

These 36 historical layouts are optional starting units, not a closed menu, a complete representation library or a reason to express every document as nodes and arrows. Choose from [Representation selection](representation-selection.md) first. If no page fits, build native prose, tables, quantitative marks, annotations, formulas or spatial views directly. [Composition examples](../assets/drawio/composition-examples.drawio) show additional combinations; adapt only what answers the reading task. Visual conventions are maintained once in [Visual grammar](visual-grammar.md).

## Selection rules

Use actor lanes for responsibility handoffs; a sequence diagram for ordered messages and response timing; a state diagram for allowed states/transitions. A decision diamond merges alternative paths; a parallel fork/join requires an explicit split/join and synchronization condition. Do not label them interchangeable or imply that flowcharts categorically cannot express concurrency.

A hierarchy expresses parent/child membership, a mind map categorizes, a concept map labels a relationship, and a boundary map expresses containment. A table compares aligned criteria. A timeline locates events in time; Gantt bars express durations; a roadmap expresses planned outcomes. Keep speculative dates labeled.

Fishbone/5 Why collect causal hypotheses, not verified causes. A funnel requires cohort/period/denominator consistency. A Venn diagram's area is not a quantity unless it is deliberately proportional. SWOT, canvases and prioritization grids need source/assumption labels. ER/class templates here are simplified teaching layouts, not complete standard UML/ER notation; add verified relationship notation when needed.

## Available editable templates

The canonical portable assets are `assets/drawio/structure-templates.drawio` (36 named pages), `assets/drawio/diagram-explainer.drawio-library.xml` (36 editable library items), and `assets/drawio/index.json`. The school Google Drive [36-page original](https://drive.google.com/file/d/1HW0ep_lNOPdE2lDby5hrDJunaNVQc_0n/view) is the preferred accessible copy. Individual `.drawio` working templates are backed up under `iCloud Drive/diagrams/diagram-explainer/templates/` on this Mac. Do not overwrite a user-edited remote or local copy. Select the minimum useful page/item, copy it into a new output and replace placeholders with verified facts.

| File | Structure | When to use / caution |
|---|---|---|
| `flow.drawio` | 조건 분기 순서도 | 순서와 조건을 읽습니다. 모든 분기에 조건과 결과를 적으세요. |
| `swimlane.drawio` | 역할별 흐름 | 행은 책임 주체입니다. 화살표가 행을 건너면 인계입니다. |
| `sequence.drawio` | 메시지 시퀀스 | 위에서 아래로 시간이 흐릅니다. 요청·응답을 별도로 표시하세요. |
| `state.drawio` | 상태 전이 | 상태 상자는 작업이 아닙니다. 전이 화살표에 사건과 조건을 적으세요. |
| `hierarchy.drawio` | 계층과 조직 | 선은 소속 관계입니다. 위계와 실행 순서를 혼동하지 마세요. |
| `mindmap.drawio` | 마인드맵 | 주제에서 범주를 펼칩니다. 가지는 원인이나 실행 순서를 뜻하지 않습니다. |
| `concept.drawio` | 개념 관계 지도 | 연결마다 관계를 동사로 적으세요. 소속과 의존을 구별하세요. |
| `architecture.drawio` | 시스템 경계 지도 | 실행 환경·책임 경계와 경계를 넘는 데이터를 표시하세요. |
| `dfd.drawio` | 데이터 흐름 | 외부 주체·처리·저장소를 구별하고 화살표에는 데이터명을 적으세요. |
| `er.drawio` | 데이터 관계 | 엔터티·키·관계 수를 표시하세요. 1:N은 호출 순서가 아닙니다. |
| `class.drawio` | 클래스 구조 | 이름·속성·동작을 나눕니다. 상속·구성·의존은 이름으로 구별하세요. |
| `network.drawio` | 네트워크 연결 | 선은 연결입니다. 실제 전송 순서·보안 보장은 별도로 설명하세요. |
| `cycle.drawio` | 반복 주기 | 주기의 시작·회귀 조건과 종료 조건을 적으세요. |
| `feedback.drawio` | 피드백 고리 | 변수가 변하는 방향과 지연을 표시하세요. 인과관계는 출처가 필요합니다. |
| `timeline.drawio` | 사건 타임라인 | 위치는 시간입니다. 날짜 미확인은 명시하고 순서만으로 인과를 단정하지 마세요. |
| `gantt.drawio` | 작업 기간 | 막대는 기간입니다. 선후 의존·마감·미확정 기간은 별도로 표시하세요. |
| `roadmap.drawio` | 목표별 로드맵 | 기간별 기대 결과를 표시하세요. 예시는 확정 일정이 아닙니다. |
| `beforeafter.drawio` | 전후 상태 | 같은 항목과 단위로 비교하고, 바뀐 값과 불변 조건을 분리하세요. |
| `comparison.drawio` | 기준별 비교표 | 같은 기준으로 비교합니다. 빈칸은 미확인이지 기능 없음이 아닙니다. |
| `raci.drawio` | 책임 배분표 | R 수행·A 최종 책임·C 협의·I 공유. 미확인 책임자는 추정하지 마세요. |
| `matrix.drawio` | 두 축 우선순위 | 축의 정의와 단위를 먼저 적고, 배치의 근거를 남기세요. |
| `swot.drawio` | SWOT | 내부 강점·약점과 외부 기회·위협을 나누세요. 근거 없는 진단은 가정입니다. |
| `fishbone.drawio` | 원인 후보 분석 | 뼈대는 원인 후보입니다. 검증된 원인과 가설을 구별하세요. |
| `why.drawio` | 5 Why 탐색 | 연속 질문은 가설을 좁히는 도구입니다. 다섯 단계가 증명을 보장하지 않습니다. |
| `funnel.drawio` | 단계별 퍼널 | 정의된 대상 집합·기간·분모를 유지합니다. 숫자는 확인 후 채우세요. |
| `venn.drawio` | 겹치는 집합 | 겹침은 교집합입니다. 면적은 수량을 뜻하지 않는 개념도입니다. |
| `containment.drawio` | 중첩된 범위 | 안에 있다는 것은 포함 관계입니다. 화살표 순서와 구별하세요. |
| `sipoc.drawio` | SIPOC | 공급자 → 입력 → 처리 → 출력 → 고객. 각 경계에서 전달물을 적으세요. |
| `journey.drawio` | 사용자 여정 | 단계별 행동·접점·경험·문제를 표시하고 관찰과 가설을 구분하세요. |
| `blueprint.drawio` | 서비스 블루프린트 | 사용자·보이는 서비스·보이지 않는 운영을 나누고 가시성 경계를 표시하세요. |
| `canvas.drawio` | 비즈니스 모델 캔버스 | 가치·고객·실행·비용·수익의 관계를 검토합니다. 모든 칸이 사실은 아닙니다. |
| `lean.drawio` | 린 캔버스 | 문제·해결·지표·고객 가설을 분리하고 검증 상태를 남기세요. |
| `affinity.drawio` | 아이디어 묶기 | 유사성으로 묶습니다. 묶음 이름은 자료에서 도출하고 인과로 읽지 마세요. |
| `kanban.drawio` | 작업 상태 보드 | 열은 상태입니다. 담당자·완료 기준을 적고 이동은 실제 진행에 맞추세요. |
| `wireframe.drawio` | 화면 구성 | 화면 영역·정보 위계·다음 행동을 표현합니다. 구현 완료를 뜻하지 않습니다. |
| `opportunity.drawio` | 기회와 해결책 트리 | 목표 → 기회 → 해결책 → 검증. 각 연결의 근거를 확인하세요. |

## Representative source entry points

[DFD](https://whimsical.com/templates/data-flow-diagram-dfd), [ER](https://whimsical.com/templates/entity-relationship-diagram), [decision tree](https://whimsical.com/templates/decision-tree), [swimlane](https://whimsical.com/templates/swimlane-diagram), [concept map](https://whimsical.com/templates/concept-map-template), [state diagram](https://whimsical.com/templates/uml-state-diagram), [customer journey](https://whimsical.com/templates/customer-journey-map), [RACI](https://whimsical.com/templates/raci-matrix), [fishbone](https://whimsical.com/templates/fishbone-diagram), [5 Whys](https://whimsical.com/templates/5-whys), [Gantt](https://whimsical.com/templates/gantt-chart-in-project-management), [Venn](https://whimsical.com/templates/venn-diagram), [business canvas](https://whimsical.com/templates/business-model-canvas), [lean canvas](https://whimsical.com/templates/lean-canvas), [SIPOC](https://whimsical.com/templates/sipoc), [opportunity tree](https://whimsical.com/templates/opportunity-solution-tree). These links were catalogued; their full boards were not all visually studied.

## Reuse and migration provenance

Copy the bundled native page or library item rather than rebuilding the entire catalogue. The 36 layouts were converted from this skill's own generated Excalidraw teaching masters, preserving editable shapes, Korean labels, connectors and source/target IDs. Bound text became the native draw.io node label; table cells are rounded with a small gap. The user’s old boards were not migrated. `scripts/build_drawio_templates.py <generated-master-folder> <new-output-folder>` is a historical conversion helper and refuses overwriting changed files. The legacy Excalidraw generator is retained for historical files, not the default creation route.

All 36 native files and library items were parsed and read back; representative flow, architecture, rounded comparison and sequence layouts were rendered with the official draw.io Desktop. Other layouts have structural checks, not an assertion of exhaustive visual approval. yEd Live is separately verified with a Korean GraphML sample; the catalogue is not an automatic yEd format converter.

## Regenerate portable teaching templates

Prefer copying the supplied native draw.io assets. Regeneration is optional: `scripts/build_templates.py` requires Python with Pillow plus an explicit `--font-file /verified/font/file` and its actual `--font-family` (default: 나눔손글씨 다행체). No font is bundled or installed. Resolve this skill directory first and use an absolute script path; do not assume a Mac font path exists in cloud. Generate to a new working folder, then run `scripts/build_drawio_templates.py` with that complete 36-template source folder and a separate output folder. Preserve user-edited templates. A substitute font test checks structure only; it does not verify the preferred Korean typeface.

The `file` values in `assets/drawio/index.json` name the historical individual working templates, which are not bundled here. Use each entry's `id` to select the matching page in `structure-templates.drawio`, or its title to select the corresponding library item. Do not report the individual file as present.
