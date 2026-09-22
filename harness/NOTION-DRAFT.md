# 현재 상태: Draft — 개인용 Codex Harness 운영 안내

2026-09-22 기준 로컬 초안이다. 상태 저장·복구 회귀검사 30개가 통과했고 실제 문서·개발 worker가 결과물을 만들었다. 이 문서의 최신 검토 상태와 고정 해시는 `doc-pilot` 상태에서 확인한다. Notion 게시는 사용자 승인 대기이며, 원격 동기화를 완료하지 않았다.

| 속성 | 값 |
| --- | --- |
| Owner | Seojun Maeng |
| Approved by | pending |
| Type / Category | How-To / Operations |
| Tags | Codex, harness, 개인 작업 |
| Status / Updated | Draft / 2026-09-22 |
| 제안된 목적지 | 개인 [Project 페이지](https://www.notion.so/317e203190cd80d68b25e72777962446), ID `317e2031-90cd-80d6-8b25-e72777962446`; 게시 위치·범위 승인 전 |
| 게시 대조용 표식 | `harness-task:doc-pilot` |

## 무엇을 하는가

문서·코딩 작업의 요청, 출처, 결과물, 검사와 게시 상태를 이어서 처리하는 로컬 작업 절차다. **실행 주체는 Codex이며 상주 데몬은 없다.** 대화를 중단하거나 Mac을 닫은 뒤에도 계속 실행된다고 가정하면 안 된다.

| 구성 | 역할과 한계 |
| --- | --- |
| 네이티브 Codex coordinator | 사용자 범위 확인, 작업자 배정, 실제 agent ID·검사 증거 기록, 승인된 게시 처리 |
| 네이티브 worker | 지정된 파일·완료 조건 안에서 결과물 작성; 이 문서 작업자의 쓰기 범위는 이 파일 하나 |
| 별도 네이티브 verifier | 고정된 결과물 해시, 요구사항, 실제 검사 증거를 받아 검토. coordinator와 모든 worker 이력의 ID와 달라야 하며 승인 시 모든 완료 조건을 포함 |
| Python/SQLite ledger | 소유권, 고정된 스킬 입력, 단계, 파일·증거 해시, 재작업 횟수와 게시 의도·영수증 보존. 모델 실행·작업자 중단·스케줄링·권한 인증은 하지 않음 |

결과물이나 증거가 바뀌면 기존 검사·검토가 무효화되고 다시 확인해야 한다. 재작업은 최대 3회다. ledger에 기록한 ID와 승인·검사 결과는 coordinator의 진술이며 실제 실행이나 사용자 동의를 독립적으로 증명하지 않는다. 실행 권한 경계는 네이티브 런타임에 있다.

## 어디에서 시작하는가

Codex의 **Being agents 프로젝트**에서 새 작업을 열고 `harness-run`을 요청한다. 기존 작업에서는 [로컬 harness-run 지침](</Users/maengseojun/Documents/ChatGPT/Being agents/.agents/skills/harness-run/SKILL.md>)을 읽도록 명시한다. 시작 요청 예시:

> harness-run으로 다음 로컬 작업을 진행해 줘: [요청]. 완료 조건은 [검증 가능한 조건]이고 수정 가능한 경로는 [파일 목록]이야. 외부 결과물은 Draft로 준비해 줘.

중단 후에는 같은 작업 ID로 재개를 요청한다. coordinator가 기존 상태·해시와 작업자 종료 여부를 먼저 확인한다. ledger의 `create`는 기록을 만들 뿐 작업자를 실행하지 않는다. 새 기록의 흐름은 `create → claim → route → worker 실행 → artifact → check → 독립 review`다.

## 실제 CLI와 소유권

아래는 [ledger.py 모듈 계약](</Users/maengseojun/Documents/ChatGPT/Being agents/harness/ledger.py>)과 `--help`에서 확인한 명령이다. 입력은 명령행 옵션이 아닌 **표준입력 JSON**이다. 기존 파일의 절대 경로를 사용하며 DB의 상위 폴더가 있어야 한다.

```sh
cd '/Users/maengseojun/Documents/ChatGPT/Being agents'
HARNESS_DB='/Users/maengseojun/Documents/ChatGPT/Being agents/.harness/pilots.sqlite'
python3 -B harness/ledger.py --help

# 실제 실행 확인: task_id만 필요하며 owner를 넣지 않는다.
python3 -B harness/ledger.py --db "$HARNESS_DB" status <<'JSON'
{"task_id":"doc-pilot"}
JSON
```

**새 작업 등록 예시 — 이번 문서 작업에서는 실행하지 않음.** 새 ID와 실제 합의한 요청·범위로 바꾼다. `create`에는 `owner`가 없고, 이후 `claim`에 실제 coordinator ID를 넣는다. `publication_required`는 게시 필요 여부이며 게시 승인이 아니다.

```sh
python3 -B harness/ledger.py --db "$HARNESS_DB" create <<'JSON'
{"task_id":"guide-example","kind":"doc","description":"승인된 로컬 문서 작성","acceptance":["합의된 문서 내용 충족"],"authorization_scope":["harness/NOTION-DRAFT.md만 수정"],"publication_required":true,"refs":[]}
JSON
python3 -B harness/ledger.py --db "$HARNESS_DB" claim <<'JSON'
{"task_id":"guide-example","owner":"REPLACE_WITH_ACTUAL_COORDINATOR_ID"}
JSON
```

`route`에는 lock의 선택된 스킬 메타데이터와 절대 로컬 경로를 전달한다. 반환된 스킬 본문을 읽고 범위에 맞게 적용한 뒤 작업자를 배정한다. 이미 있는 `doc-pilot`을 다시 생성하거나 예시 작업에 같은 파일을 동시에 배정하지 않는다.

**일시정지·재개 예시.** coordinator가 실제 두 pilot에서 같은 owner로 `pause → resume`을 실행해 새 run ID와 상태 보존을 확인했다. 아래의 다른 owner로 인계하는 예시는 별도 종료 확인이 필요하다. 다음 placeholder는 `status`에 나타난 현재 owner와 실제 재개 coordinator ID로 각각 바꾼다. 조회 당시 owner는 `01a0c854-330e-7701-a47a-811a06ad11ec`였지만 인계 직전에 다시 확인한다.

```sh
python3 -B harness/ledger.py --db "$HARNESS_DB" pause <<'JSON'
{"task_id":"doc-pilot","owner":"REPLACE_WITH_CURRENT_OWNER_ID"}
JSON
python3 -B harness/ledger.py --db "$HARNESS_DB" resume <<'JSON'
{"task_id":"doc-pilot","owner":"REPLACE_WITH_RESUMING_COORDINATOR_ID"}
JSON
```

`pause`는 현재 owner가 기록을 정지시키는 명령이며 worker를 중단하지 않고 owner 필드도 지우지 않는다. coordinator가 네이티브 도구로 기존 worker를 중단하고 종료를 확인한 뒤에만 같은 파일의 작업을 넘긴다. 명시적 pause 이후 `resume`이 소유권을 다시 확보하고 새 run ID를 만든다. 임의의 owner 문자열로 소유권을 우회하거나 DB를 직접 편집하지 않는다. 복구 시 DB와 journal을 함께 보존한다.

## 출처 로딩·설치·실행의 구분

아래 upstream은 모두 실제 `openai/skills` 저장소의 불변 commit **`49f948faa9258a0c61caceaf225e179651397431`**에 고정되어 있다. GitHub 조회 이력은 환경 감사에 기록되어 있고, 이번 작업은 네트워크 재조회 없이 로컬 원문과 해시를 확인했다.

| 원문 | 이 작업에서의 의미 |
| --- | --- |
| [Skill Creator](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.system/skill-creator/SKILL.md) | 로컬 harness-run 작성에 사용된 upstream; 이번 문서의 routed skill은 아님 |
| [Notion Knowledge Capture](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/notion-knowledge-capture/SKILL.md) | 이번 `doc-pilot`에 실제 전달된 고정 본문. 요약·소유자·상태·출처·변경 기록 구조를 적용 |
| [Documentation Database 참조](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/notion-knowledge-capture/reference/documentation-database.md) | 문서 속성 참고. 사용자 범위에 따라 데이터베이스·Notion 작업 생성은 수행하지 않음 |
| [CLI Creator](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.curated/cli-creator/SKILL.md) | lock에 있는 별도 코딩 파일럿용 원문. 이번 문서에 적용하거나 실행 완료로 판정하지 않음 |

- **소스 로딩:** `sync_skills.py`가 고정 파일을 `.harness/skills`에 보관하고, `route`가 검증한 선택 본문을 ledger 컨텍스트에 고정한다. `--check`는 다운로드 없이 캐시 무결성만 검사한다.
- **설치·발견:** `.agents/skills/harness-run/SKILL.md`의 로컬 배치와 실제 Codex 목록 발견은 확인됐다. upstream 파일 캐시나 Notion 링크만으로 전역 스킬 설치·동기화가 완료되는 것은 아니다. 자체 harness/skill의 개인 GitHub 게시도 미완료다.
- **실행:** 네이티브 worker가 해당 지침을 읽고 실제 산출물을 만들며 별도 verifier가 검토해야 한다. 발견 성공·소스 다운로드·해시 통과만으로 작업 성공이나 원격 게시를 인정하지 않는다. 스킬 본문은 이 문서에 복제하지 않는다.

## 확인된 범위와 남은 검증

| 구분 | 근거와 현재 상태 |
| --- | --- |
| 로컬 구현 확인 | ledger의 소유권·고정 입력·해시 검사·독립 검토·재작업 제한·게시 기록 경로를 코드에서 확인. 로컬 파일 게시는 기존 다른 내용을 덮어쓰지 않는 생성·재조회 경로를 갖춤 |
| 이번 작업에서 실행 확인 | `python3 -B harness/ledger.py --help`와 기존 DB의 `status`가 종료 코드 0. 조회 전후 DB·잠금 파일 바이트 불변. `python3 -B harness/sync_skills.py --check`에서 9개 파일 검증; routed 본문과 로컬 스킬·SHA-256 일치 |
| coordinator의 추가 검증 | 전체 unittest 30개 통과: 동일 요청 재전달, 실제 subprocess 종료 뒤 파일 저장 복구, 기록만 재시도, 변경된 결과/증거 무효화, 인증·권한 blocker, 동시 실행·게시, 사용자 수정 보존. 실제 두 pilot의 `pause → resume`도 통과. 원격 저장 검증과는 구분한다. 근거: `.harness/core-check.txt`, `.harness/control-check.json` |
| 원격 게시 승인 대기 | 개인 Project는 후보 목적지다. 정확한 생성/수정 대상·범위와 최종 결과물 해시에 결합된 사용자 승인, 게시 후 원문·상태 재조회 및 영수증이 필요 |
| Endix 정책 미확인 | 2026-09-22 환경 감사에서 Linear `END-464` 조회가 `USER_NOT_LOGGED_IN`으로 실패. 팀 소유자·승인·문서 동기화 규칙은 확인되지 않았으며, 이 문서는 Endix 팀 정책이나 팀 자동화 승인이 아님 |

원격 `publish`는 `reconciliation-required`라는 대조 필요 상태를 기록할 뿐 Notion/GitHub/Linear에 전송하지 않는다. 승인 후에도 저장 직전에 대상을 다시 읽고, 결과가 불확실하면 `harness-task:doc-pilot` 표식과 대상·내용을 대조한다. 확인 없이 새 페이지를 반복 생성하지 않는다. 정확히 한 번만 게시되거나 원격 동시 수정이 방지된다고 보장하지 않는다. 필수 게시 영수증이 없으면 전체 작업 완료로 처리하지 않는다.

## 근거 파일

[routed context](</Users/maengseojun/Documents/ChatGPT/Being agents/.harness/pilot-inputs/doc-pilot-context.json>), [harness-run](</Users/maengseojun/Documents/ChatGPT/Being agents/.agents/skills/harness-run/SKILL.md>), [ledger 계약·구현](</Users/maengseojun/Documents/ChatGPT/Being agents/harness/ledger.py>), [source lock](</Users/maengseojun/Documents/ChatGPT/Being agents/harness/skills.lock.json>), [README](</Users/maengseojun/Documents/ChatGPT/Being agents/harness/README.md>), [환경 감사](</Users/maengseojun/Documents/ChatGPT/Being agents/audit/harness-environment-2026-09-22.md>), [로컬 스킬 발견 기록](</Users/maengseojun/Documents/ChatGPT/Being agents/.harness/skill-discovery.json>). 로컬 링크는 이 Mac에서 확인하는 증거 경로이며 Notion 첨부·원격 동기화 링크가 아니다.

## 변경 기록

- 2026-09-22 — 개인용 Draft 최초 작성. 실제 routed skill, 고정 upstream 출처, 시작·상태·중단·재개 절차와 로컬 검증/원격 승인 경계를 기록. 검토 결과와 최종 해시는 ledger에서 별도 확인.
