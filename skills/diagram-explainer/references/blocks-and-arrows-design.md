# Blocks & Arrows 디자인을 diagrams.net·yEd Live에 적용하기

2026-10-10 사용자 요청: 일반 사각형 대신 둥근 모서리. 실선·점선·화살표를 의미에 맞게 활용. Blocks & Arrows의 디자인 요소를 적극 반영한다. 기본 출력은 diagrams.net, 자동 그래프 배치는 yEd Live를 사용하며, 한국어는 등록된 나눔손글씨 다행체를 사용한다.

## 직접 확인한 디자인 → 구현

아래는 목록 제목만 읽은 예시와 구별되는 실제 화면 관찰이다. 화면에 보인 디자인을 적용하며, 보안·인증·의료 등 예시 내용의 정확성을 보증하지 않는다. 긴 보드 일부는 화면 하단 안내에 가려졌으므로 전체 보드를 검사했다고 주장하지 않는다.

| 실제 화면 출처 | 관찰한 요소 | 편집 가능한 구현 |
|---|---|---|
| [API gateway/auth](https://blocksandarrows.com/diagrams/band/api-gateway-auth-microservices-architecture-diagram-ywr7) | 점선 외곽 경계, 경계 안의 서비스, 저장소·서비스 아이콘, 데이터명을 적은 연결 | 둥근 점선 enclosure + 경계 제목, 역할이 다른 도형, 데이터명 화살표 |
| [API request/response](https://blocksandarrows.com/diagrams/band/api-request-response-flow-band-architecture-pc34) | 둥근 색상 노드, 외부 주체 아이콘, 원통형 저장소, 꺾이는 경로, 별도 요청·반환 경로 | `architecture`: 사용자 아이콘, 둥근 서비스, 원통형 저장소, 반환 우회선. 원본의 모든 반환선이 점선인 것은 아니며, 우리 양식은 범례로 점선 반환을 선언 |
| [Object-oriented design](https://blocksandarrows.com/diagrams/band/object-oriented-design-class-diagram-web-app-559w) | Ops/HR 점선 군집, 이름이 붙은 관계, 서로 다른 노드 색, 둥근 모서리 | 역할 군집과 색을 일관되게 사용. 상속·의존·소속의 표기는 관계에 맞게 선택하고 색만으로 구분하지 않음 |
| [Email OAuth2 sequence](https://blocksandarrows.com/diagrams/sequence/email-oauth2-quick-signup-flow-61rg) | 정렬된 참여자, 세로 생명선, 위→아래 메시지, 선 위의 짧은 이름 | `sequence`: 둥근 참여자 머리글, 분리된 요청·반환, 생명선·활성 구간, 지역 범례. 원본의 날카로운 머리글은 사용자의 둥근 모서리 선호로 변경 |
| [JIT inventory mind map](https://blocksandarrows.com/diagrams/mindmap/z075f721z2am0pgv) | 큰 중심 원형 주제, 주변 타원 범주, 가지별 색 | `mindmap`: 중심과 주변 범주, 머리 없는 관계선, 범주색. 원본의 겹친 도형과 끊긴 단어는 복제하지 않고 간격 확보 |
| [Patient management / ER](https://blocksandarrows.com/diagrams/band/band-er-patient-management-process-diagram-19r5) | 상단 색 띠와 필드 행이 있는 엔터티, 키 표식, 1:N 꺾인 관계, 둥근 점선 묶음 | `er`, `class`: 독립된 둥근 레코드, 제목 띠, 속성·동작 구획, PK/FK 텍스트, 관계 수. 목록의 process 이름만으로 순서도로 분류하지 않음 |

## 모서리와 표면

- 일반 노드·카드·주석·버튼·헤더·외곽 그룹은 draw.io의 `rounded=1;arcSize=16`, yEd의 `ROUND_RECTANGLE`를 기본으로 둔다. 동그라미·마름모·원통 등 의미가 있는 다른 도형도 사용한다.
- 원통은 편집 가능한 본체와 두 타원을 묶어 표현한다. 본체의 내부 직선은 원통 표기의 일부이며, 보이는 일반 사각 노드를 다시 날카롭게 만드는 예외로 쓰지 않는다.
- 제목 띠 + 본문 행 + 얇은 구분선으로 구조를 보인다. 긴 설명을 작은 노드에 넣지 않는다. 둥근 카드형 표 셀을 선택한 경우 간격을 확보한다. 일반 데이터 표는 정렬·여백·얇은 구분선으로 읽을 수 있으며 모든 셀을 카드로 만들 필요는 없다.
- 검은색 계열 글자·윤곽과 역할별 소수의 색을 사용한다. 강한 강조는 핵심 경로·변경점에만 사용한다. 아이콘에는 항상 이름을 함께 둔다.
- 구현에 없는 의미 없는 장식은 추가하지 않는다. 사용자·저장소 등 역할을 알아보기 위한 작은 편집 가능 기호는 적극 사용한다.

## 관계선과 문서 표현의 범위

공통 선·논리·범위·주석 표기는 [Visual grammar](visual-grammar.md)에 둔다. 이 사이트의 서비스·관계 그림은 필요한 관계 정보를 표현할 때 참고한다. 모든 문서에 서비스 상자·아이콘·화살표를 도입하는 기본값이 아니다. 정량 비교와 문서 구성을 위해 [Visual reference library](visual-reference-library.md)의 다른 사이트와 결합해 표현을 선택한다.

2026-10-13 all 목록과 API gateway/auth 상세를 다시 읽고 화면을 검사했다. 실제 Backend 경계와 data/authorize/query 관계는 보였으나 일부 아이콘은 로드되지 않았고 하단 안내가 일부 가렸다. 2026-10-10의 상세 관찰과 최신 접근 범위를 구분한다. 목록 카드를 클릭하면 dashboard로 연결될 수 있어 상세 URL로 확인했으며, 모든 catalog 예시를 검사하지 않았다.

## 적용과 검사

36개 양식의 일반 사각형에 둥근 모서리를 적용했다. `flow`에는 실선 실행/점선 대안과 범례, `architecture`에는 사용자·서비스·저장소·주석·반환 경로, `dfd`에는 처리/저장소 구별, `network`에는 방향 없는 연결, `sequence`에는 활성 구간과 범례, `er`/`class`에는 제목·필드 구획, `mindmap`에는 범주색과 도형 사이 가지를 적용했다.

기존 파일이 생성본과 같은지 먼저 비교하고 백업한 뒤 갱신한다. 수정된 사용자 파일이 있으면 덮어쓰지 않는다. 구조 검사와 앱에서의 실제 렌더 검사를 구별한다. 전환된 .drawio 36종과 라이브러리는 구조·재조회 검사를 통과했고, flow/architecture/comparison/sequence는 공식 draw.io Desktop에서 한글 렌더를 확인했다. 전체 36종의 시각적 승인을 뜻하지 않는다. yEd Live는 별도 GraphML 한글 샘플로 확인한다.
