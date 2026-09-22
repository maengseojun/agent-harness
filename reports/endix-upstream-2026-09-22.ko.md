## Endix에 적용할 오픈소스 변경·토론 검토

조사일: 2026-09-22. 상태: 개인 검토 초안. 범위: 현재 로컬 Endix 계약과 실제 고정 의존성을 대조한 네 가지 점검 항목. 배포된 계약의 취약성 판정이나 전체 보안 감사는 아니다.

가장 먼저 점검할 것은 **USDC 단위가 바뀌는 경계**와 **요청 성공 후 실제 체결을 확인하는 절차**다. 반대로 상위 저장소의 소수점 버그와 OpenZeppelin import 변경은 현재 Endix 코드에 대조하면 무조건 수정할 사안이 아니다. 변경 목록을 그대로 이슈로 옮기지 않고, 이미 반영된 수정과 추가 검증이 필요한 항목을 나눴다.

## 조사 기준과 버전

- Endix 기준 경로: `Endix_V1/dev/contracts`. HEAD: `1919aa3d25e88a4fcd0a03ae00328b5b93fd795c`.
- 작업 중 수정된 파일이 있는 checkout이다. 아래 코드 위치는 조사 당시 작업 사본 기준이며 HEAD의 배포 코드라고 단정하지 않는다. 관련 파일의 SHA256과 변경 목록은 로컬 증거 `project-snapshot.json`에 저장했다.
- 실제 HyperEVM 의존성은 `endix-foundation-v1/hyper-evm-toolkit`의 `e5b6e9c4a0f0c08e059a4e93874f85d432e1551c`다. 공개 upstream `hyperliquid-dev/hyper-evm-lib`의 main과 다르다.
- OpenZeppelin Contracts: `fcbae5394ae8ad52d8e580a3477db99814b9d565`, 패키지 버전 5.5.0. Contracts Upgradeable: `aa677e9d28ed78fc427ec47ba2baef2030c58e7c`, v5.5.0.
- 수집 범위: hyper-evm-lib 기본 브랜치 최근 commit 10건, 생성순 issue/PR 20건과 관련 본문·댓글·diff; OpenZeppelin 최근 commit 5건과 사용 버전에 직접 관련된 PR #5944 및 로컬 changelog. 전체 페이지를 순회하거나 별도 GitHub Discussions 전체를 검색하지 않았다. 여기서 토론은 issue/PR 댓글을 뜻한다.
- 상태·날짜는 GitHub API로 확인했다. GitHub 날짜는 UTC, 로컬 fork commit 날짜는 기록된 +09:00 기준이다. 최신 목록은 탐색에 쓰고, 아래 네 항목은 Endix의 실제 의존성과 연결되는 정도로 선정했다. 특정 기간의 모든 변경을 망라한 목록은 아니다.

증거 표기: VERIFIED는 직접 읽은 코드·도구 결과, DOCUMENTED는 upstream 문서·제보, INFERRED는 그로부터의 추론, RECOMMENDATION은 제안, UNKNOWN은 확인하지 않은 사항이다.

## 1. USDC 6자리와 Core 8자리 단위를 명시해야 한다

**DOCUMENTED:** [hyper-evm-lib issue #32](https://github.com/hyperliquid-dev/hyper-evm-lib/issues/32)는 2026-05-12 생성됐으며 조사 시점에도 open이다. 제보자는 USDC 입금과 EVM 복귀 경로의 단위 해석 차이를 설명했다. [후속 댓글](https://github.com/hyperliquid-dev/hyper-evm-lib/issues/32#issuecomment-4433226513)은 기존 사용처 영향을 줄이기 위해 동작보다 문서를 바꾸자는 의견이다. 제보와 의견을 수정 완료나 공식 취약성 확정으로 해석하지 않았다.

**VERIFIED / 적용 판정: 그대로 재현된 버그가 아니라, 단위 경계를 검증할 근거.** Endix fork의 `src/common/HLConversions.sol:15`는 token metadata의 `evmExtraWeiDecimals`에 따라 변환하며, 해당 제보가 지목한 USDC identity-cast 특례가 없다. `src/CoreWriterLib.sol:73`의 `bridgeUsdcToCoreFor`는 EVM 단위 금액을 `depositFor`에 넘긴다. 반면 `bridgeToEvm`의 90행 이후는 `isEvmAmount`에 따라 변환 여부가 갈린다. Endix `src/vault/EndixVault.sol:165`의 호출도 이 경계를 통과한다.

**RECOMMENDATION:** 호출 경로마다 EVM raw, Core raw, 표시용 human 단위를 명시하고, 알려진 metadata fixture에서 1 USDC의 입금과 반환을 확인한다. 6자리 EVM 값 `1_000_000`과 8자리 Core 값 `100_000_000`을 혼동했을 때 검사가 실패해야 한다. `isEvmAmount=true/false`, 0으로 잘리는 dust, 최대 uint64 경계도 구분한다. round-trip에서 같은 변환 함수를 양쪽 기대값에 쓰기만 하면 공통 버그를 놓칠 수 있으므로 독립적인 수치 기대값이 필요하다.

현재 테스트의 출발점도 확인했다. `test/vault/EndixVault.t.sol:307` 등의 bridge 성공 사례는 0 금액으로 변환을 우회하며, toolkit `test/unit-tests/bridging/BridgingTest.t.sol:175`의 USDC 기대값은 같은 변환 함수를 사용한다. 읽은 테스트 내용이므로 fresh PASS로 표시하지 않았고, 독립 수치 기대값을 확인할 이유로 삼았다.

**UNKNOWN:** 현재 배포된 token metadata, 운영 keeper의 실제 입력 단위와 배포 bytecode는 이번에 확인하지 않았다. 이 제보만으로 Endix에서 100배 오차가 발생한다고 말할 수 없다.

## 2. 소수점 차이가 0인 경우는 현재 fork에 이미 처리돼 있다

**DOCUMENTED:** [PR #28](https://github.com/hyperliquid-dev/hyper-evm-lib/pull/28)은 2026-03-05 merged다. [merge commit](https://github.com/hyperliquid-dev/hyper-evm-lib/commit/ebb49c7fd8afafcb70233878d0c5d12c196e480b)은 EVM과 Core 소수점 차이가 0일 때 양방향 변환을 처리한다.

**VERIFIED / 적용 판정: 해당 분기 이미 반영.** Endix가 고정한 fork는 2026-02-25의 [commit e5b6e9c](https://github.com/endix-foundation-v1/hyper-evm-toolkit/commit/e5b6e9c4a0f0c08e059a4e93874f85d432e1551c)에 그 처리가 있다. `src/common/HLConversions.sol:25`는 0 차이에서 `SafeCast.toUint64(evmAmount)`를 반환하고, 46행은 역변환에서 동일 값을 반환한다. upstream merge SHA가 의존성 이력에 없다는 이유만으로 미수정으로 분류하면 안 된다.

**RECOMMENDATION:** 이번에는 의존성 버전을 올리거나 같은 패치를 다시 넣지 않는다. 이후 업데이트 시 소수점 차이가 음수·0·양수인 세 경우, dust, overflow를 고정 입력으로 회귀 검사한다. 변경의 의미를 비교하고 commit 포함 여부만으로 판단하지 않는 절차를 스킬에 넣었다.

**UNKNOWN:** 이 코드 분기 확인은 모든 token metadata 조합이나 실제 브리지의 안전성을 증명하지 않는다. 이번 조사에서는 Endix의 계약 테스트 전체를 재실행하지 않았다.

## 3. EVM 요청 성공과 HyperCore 실행 결과를 구분해야 한다

**DOCUMENTED:** [issue #33](https://github.com/hyperliquid-dev/hyper-evm-lib/issues/33)은 2026-05-13 생성, 2026-05-14 closed다. 제보에는 EVM 트랜잭션 성공에도 API wallet 상태가 기대대로 바뀌지 않은 사례가 있으며, [후속 댓글](https://github.com/hyperliquid-dev/hyper-evm-lib/issues/33#issuecomment-4446758441)은 wallet 활성화 조건을 언급한다. 이것을 현재 거래 실행 버그나 미해결 장애로 확대하지 않았다.

[Hyperliquid 공식 문서](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/hyperevm/interacting-with-hypercore)는 CoreWriter가 로그를 내보내고 HyperCore가 action으로 처리하며, 주문 등의 enqueue와 execution이 나뉜다고 설명한다. precompile 읽기 역시 EVM block 생성 시점의 HyperCore 상태를 반영한다.

**VERIFIED / 적용 판정: 비동기 확인 경계에 직접 관련.** Endix의 현재 `src/executor/VaultTradeEngine.sol:646` wrapper는 모듈에 위임한다. 실제 단건 확인은 1587행, 일괄 확인은 1609행, fill 검사는 2160행의 모듈 구현이다. keeper가 성공 여부 bool을 넣는 방식이 아니라 CLOID를 넣으면 계약이 잔고 증가를 검사한다. 출력 자산 잔고의 증가량이 최소 기준 이상이면 확인하며, 초기 `minFillBps`는 500, 즉 5%다. 이는 주문별 체결 응답이나 100% 체결의 증명과는 범위가 다르다.

일괄 확인은 미존재·비-PENDING 항목을 false로 남기지만, PENDING 항목의 fill 검사 실패는 전체 호출을 revert시킨다. `test/executor/VaultTradeEngineHardening.t.sol:830`에는 잔고 증가 없음 거부, 939행 이후에는 dust 거부 및 10% 부분 체결 허용 테스트가 있다. 이번 검색에서 `src`, `test`, `script` 내부의 `confirmTradeChunks` 호출 테스트는 찾지 못했다. 기존 통합 테스트는 simulator 잔고를 강제로 바꾸고 단건 확인을 호출하므로 실제 주문별 귀속이나 batch 실행의 검증으로 확대하지 않았다.

**RECOMMENDATION:** 기존 잔고 증가 검사를 출발점으로, 같은 출력 자산을 쓰는 여러 chunk와 무관한 입금이 주문별 확인에 어떤 영향을 주는지 재현한다. batch에는 유효·미체결·중복 CLOID를 함께 넣어 전체 revert와 재시도 동작을 확인한다. 부분 체결, 늦은 확인, timeout 직후 확인, keeper 재시작도 기존 검사와 연결한다. API wallet 제보의 재현과 Endix 체결 검증은 별개의 테스트이며, 이번 관찰만으로 악용 가능한 취약성이 입증된 것은 아니다.

**UNKNOWN:** 운영 keeper가 어떤 데이터로 확인을 호출하는지와 배포 환경의 end-to-end 정산은 이번 코드 열람만으로 검증되지 않는다. 새 모니터링 서비스를 만드는 대신 기존 keeper·상태 전이 검사에서 먼저 확인할 항목이다.

## 4. ReentrancyGuard import 이름만 보고 잘못된 업그레이드를 제안하지 않는다

**DOCUMENTED:** OpenZeppelin [PR #5944](https://github.com/OpenZeppelin/openzeppelin-contracts/pull/5944)는 2025-09-24 merged이며 [commit efd1878](https://github.com/OpenZeppelin/openzeppelin-contracts/commit/efd187888de78f255747fc6259bdda0fac7a346e)로 반영됐다. v5.5.0 changelog는 해당 guard의 upgradeable 변형을 일반 패키지 import로 바꾸도록 설명한다. 여기서 stateless 표기는 guard가 저장소를 전혀 쓰지 않는다는 뜻으로 해석하면 안 된다.

**VERIFIED / 적용 판정: 현재 import와 해당 버전 지침은 부합.** Endix `MintRedeemRouter.sol:7`과 `VaultTradeEngine.sol:7`은 `@openzeppelin/contracts/utils/ReentrancyGuard.sol`을 사용한다. 고정된 v5.5.0 구현은 전용 storage slot을 쓰고 entered 상태를 검사한다. 따라서 “Upgradeable 접미사가 없으니 취약”이라는 판정은 근거가 부족하다.

기존 `test/router/MintRedeemRouterFeePolicy.t.sol:160`에는 callback 재진입 시도와 guard 오류를 확인하는 테스트가 있다. 이를 읽었지만 실행하지 않았다. 현재 guard의 소스는 entered 값 2만 거부하므로, proxy 저장소 초기값이 0이라는 사실만으로 첫 호출이 불가능하다고 판단할 수도 없다.

**RECOMMENDATION:** 실제 이전 구현과 새 구현의 storage layout, delegatecall 모듈의 guard slot 공유, 최초 proxy 호출·재진입을 검사한다. transient guard로 바꾸려면 대상 chain의 EIP-1153 지원을 별도로 확인한다. 이름을 맞추기 위한 교체나 최신 major 버전 일괄 적용은 이번 과제에서 하지 않는다.

**UNKNOWN:** 현재 배포 proxy와 과거 업그레이드 경로까지 안전하다는 결론은 아니다. 이번에 배포 storage를 읽거나 업그레이드를 실행하지 않았다.

## 다음 작업 우선순위

1. USDC 경계: 입금·출금 호출의 단위와 독립 기대값 검사를 확인한다. 완료 기준은 정상 수량 보존과 의도적인 100배 입력 오류 검출이다.
2. 체결 확인: 잔고 증가의 주문별 귀속, batch의 혼합 입력과 전체 revert, keeper의 재시도 절차를 확인한다. 완료 기준은 unrelated 입금·중복 확인이 잘못 귀속되지 않고 재시작 후 같은 결과로 수렴하는 것이다.
3. 의존성 갱신 시: 이미 있는 0 소수점 처리와 v5.5.0 guard 사용을 보존한다. 완료 기준은 관련 회귀 검사와 실제 upgrade layout 검증이다.

위 항목은 제안된 후속 검사이며 실행 완료된 계약 테스트 목록이 아니다. 조사 때문에 Endix 소스·설정·의존성을 수정하지 않았다.

## 재사용과 연동 테스트 범위

재사용 스킬 이름은 `blockchain-upstream-review`다. 특정 프로젝트 이름이나 일회성 이슈 상태를 스킬 규칙으로 고정하지 않고, 실제 의존성 확인 → 원문 확인 → 적용 여부 판정 → 최소 검사 → 승인된 저장 위치와 readback 절차를 담았다.

이번 실행은 Being agents 밖의 별도 로컬 작업 폴더에서 전역 harness를 사용한다. GitHub는 개인 비공개 `maengseojun/agent-harness`의 별도 브랜치, Notion은 개인 `나 / Project` 아래 새 초안을 대상으로 한다. GitHub 저장 파일과 Notion 본문을 실제로 다시 읽은 뒤 별도 실행 기록에 결과를 남긴다. 로그인 여부와 저장 완료를 구분하며, 이 본문만으로 아직 수행하지 않은 게시 검증을 성공이라 주장하지 않는다.

이 테스트는 현재 컴퓨터의 Codex 실행과 연결된 GitHub·Notion에 한정된다. 다른 컴퓨터나 Work cloud로 전역 스킬·인증·진행 기록이 자동 동기화되는지는 검증하지 않는다.

스킬 원본: [blockchain-upstream-review / 고정 commit](https://github.com/maengseojun/agent-harness/blob/e92575790e3114a8dc8137d138819686ce933a86/.agents/skills/blockchain-upstream-review/SKILL.md). 해당 commit의 원격 존재 여부와 저장 내용은 게시 후 readback으로 확인한다.
