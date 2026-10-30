# Handoff: Defect-Rate Chatbot — 요청 처리 흐름 아키텍처 다이어그램

## Overview
불량률 예측/최적화 챗봇의 요청 처리 흐름(QueryExtractor → `DefectRatePipeline.run()` intent 분기 → 4개 경로)을 시각화한 **정적 아키텍처 다이어그램(SVG)** 입니다. 설계 문서·위키·README·발표 자료에 삽입하여 팀원이 intent별 분기, 외부 API 호출 지점, status 반환 값을 한눈에 파악하도록 하는 것이 목적입니다.

## About the Design Files
이 번들의 파일은 **HTML/SVG로 작성된 디자인 레퍼런스**입니다. 최종 산출물 자체가 SVG 이미지이므로 대부분의 경우 `defect-chatbot-architecture.svg`를 그대로 문서에 삽입하면 됩니다.
만약 다이어그램을 코드베이스 안에서 재구현해야 한다면(예: Mermaid, draw.io, React Flow, D2, PlantUML 등으로 유지보수하기 위해), 이 SVG를 기준 레퍼런스로 삼아 해당 환경의 기존 도구·패턴으로 다시 그리세요. 별도 환경이 없다면 텍스트로 버전 관리가 쉬운 **Mermaid flowchart** 또는 **D2**를 권장합니다.

## Fidelity
**High-fidelity.** 색상·타이포·간격·레이아웃이 최종 값입니다. 재구현 시 아래 토큰과 좌표를 그대로 따르면 동일한 결과를 얻습니다.

## Screens / Views

### 1. 아키텍처 다이어그램 (단일 캔버스)
- **Canvas**: 1600 × 1880 px (`viewBox="0 0 1600 1880"`), 배경 `#f6f5f2`
- **좌우 여백**: 40px. 흐름은 위→아래, 중앙 축 x=800

#### 상단 공통 흐름 (중앙 정렬)
| 요소 | 위치/크기 (x, y, w, h) | 스타일 | 내용 |
|---|---|---|---|
| 사용자 질의 | 690,104,220,46 · radius 23 | fill `#1d1c1a`, 흰 글씨 14px bold | "사용자 질의" |
| QueryExtractor | 420,190,760,232 · r12 | 흰 박스, stroke `#1d1c1a` 1.5 | 제목 + LLM 태그 + "SDC LLM 구조화 출력" |
| 폴백 칩 | y=244, h=24, r5 | `#f4f3ef` / stroke `#d6d3ca`, mono 12px | `json_schema → json_object → prompt` |
| ① 12개 필드 추출 | y=310 | bold 14 + 회색 13 | "기존과 동일 — 추측 금지 · 모호값 처리 · 다중 레코드 분리" |
| ② intent 동시 추출 (NEW) | y=343 | NEW 배지 `#6b46c1` | intent 칩 5개: `predict`, `optimize_reduce_defect`, `optimize_find_defect_risk`, `predict_and_optimize`, `clarify` |
| enum 폴백 주석 | y=404 | 회색 13 | `스키마 enum 밖 · 누락 값 → 코드가 "clarify"로 대체` |
| llm_error 출구 | 오른쪽 1262,290 pill | 빨강 pill, 점선 화살표 | "LLM 호출 · 파싱 실패" / `status=llm_error` / "intent 문제에도 동일" |
| DefectRatePipeline.run() | 540,470,520,78 · r12, stroke 2 | mono 17 bold | 부제 "intent로 분기 — 아래 4개 경로 중 하나로" |
| 분기 버스 | y=584, x 210→1090, 분기점 원 r4 | stroke `#5f5d58` 1.6 | 경로 A/B/C 중심 x = 210 / 605 / 1090 |

#### 경로 A — clarify (x 40–380)
1. Intent 헤더(검정 박스 340×96): `INTENT` / `clarify`
2. 박스: "어떤 API도 호출하지 않음" / "방향을 되묻는 고정 문구 반환"
3. 노랑 pill `status=clarify`

#### 경로 B — optimize (x 410–800, "조건 입력 불필요")
1. Intent 헤더: `optimize_reduce_defect | optimize_find_defect_risk`
2. `target = build_target(intent)` — 고정 사전: 불량 최소화 → `"1"`, 위험 탐색 → `"0"`
3. 파란 API 박스 `OptimizationClient.optimize` — `GET $OPTIMIZATION_API_URL?target=…` · 재시도 + 타임아웃
4. 2갈래 카드(각 184×144):
   - 실패(빨강): "호출 · 파싱 실패" → `endpoint_error`
   - 성공(초록): "최적 조건 Markdown 표 + 예상 확률", "ML · LLM 미호출" → `status=ok`

#### 경로 C — predict (x 840–1340, "조건 입력 필요 (기존 AIHUB와 동일한 결)")
1. Intent 헤더: `predict | predict_and_optimize`
2. `_gather_and_predict` 박스(500×200, "공통 단계 · §4.3") — 번호 원 3단계:
   1. `SlotFillingSession.merge` — 이전 턴의 확인값과 병합
   2. `validate_provided_fields` — 값이 있는 필드만 개별 검증 (슬롯이 덜 차도 실행)
   3. `DefectRateInput` — 12개 모두 찼을 때 최종 타입 · 범위 검증
   - 오른쪽 출구(노랑, x=1382): "누락 · 모호 필드 있음" → `need_more_info` / "허용값 · 범위 위반" → `invalid_input` (둘 다 "API 미호출")
3. 데이터 박스 `{"data": [ {12개 컬럼}, ... ]}`
4. 파란 API 박스 `DefectRateMLClient.predict` — `POST $AI_HUB_ENDPOINT_URL` · 재시도 + 타임아웃 + 에코 검증
   - 출구(빨강): "호출 · 응답 검증 실패" → `endpoint_error`
5. 데이터 박스 `predictions: [1.6498…, ...]` (단위 %)
6. 하위 분기 (y=1300, x 950 / 1330):
   - **C-1 predict**: "LLM 해설" + LLM 태그, "선택 사항", `explain=false면 생략` → `status=ok`
   - **C-2 predict_and_optimize (NEW)**: `target = build_target("predict_and_optimize")` — 항상 `"1"` (불량 최소화) → `OptimizationClient.optimize` (경로 B와 동일) → 2갈래:
     - 실패 → 부분 성공: "예측 결과는 그대로 반환", `optimization=null`, "errors에 사유 기록" → 점선 테두리 초록 pill `status=ok (부분)`
     - 성공: "예측치 + 개선 조건 표" → `status=ok`

#### 범례 (40,1640,760,210)
내부 처리 단계 / 외부 API 호출 / intent 분기 / 데이터 페이로드 · ok / halt(추가 입력·확인 필요, API 미호출) / error · NEW 배지 · LLM 태그 · 실패 경로(점선)

## Interactions & Behavior
정적 이미지 — 인터랙션 없음. 반응형 필요 시 `width:100%` + viewBox로 비율 유지 스케일링(뷰어 HTML 참조, max-width 1600px).

## State Management
해당 없음(정적 다이어그램). 다이어그램이 표현하는 **도메인 status 값**은 다음과 같습니다:
`ok`, `clarify`, `need_more_info`, `invalid_input`, `llm_error`, `endpoint_error` (+ predict_and_optimize의 부분 성공: `ok` + `optimization=null` + `errors[]`).

## Design Tokens
**Colors**
| 용도 | Hex |
|---|---|
| 배경 | `#f6f5f2` |
| 본문/강조 텍스트, intent 헤더 fill | `#1d1c1a` |
| 보조 텍스트 | `#7a776f` |
| 헤더 내 라벨 | `#a9a69e` (구분자 `#8f8c84`) |
| 화살표/연결선 | `#5f5d58` |
| 구분선 | `#e3e0d8` |
| 칩 배경 / 테두리 | `#f4f3ef` / `#d6d3ca` |
| 카드 배경 | `#fbfaf8` |
| 데이터 박스 | `#ecebe6` / stroke `#c9c6bd` |
| 외부 API 박스 | fill `#eaf0fb`, stroke/라벨 `#3b5bab` |
| OK pill | fill `#e5f1e8`, stroke `#2f7d4f`, text `#1f5c38` |
| Halt pill | fill `#fbf1dc`, stroke `#b7791f`, text `#8a5a12` |
| Error pill | fill `#fbe9e6`, stroke `#c2412d`, text `#9a2f1f` |
| NEW 배지 | `#6b46c1` |
| LLM 태그 | fill `#efe9fb`, stroke `#6b46c1`, text `#553399` |

**Typography**
- Sans: `Pretendard, "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif`
- Mono (코드·식별자·status): `"JetBrains Mono", D2Coding, Consolas, "SF Mono", monospace`
- 스케일: 타이틀 26/700 · 부제 15 · 박스 제목 18/700 (mono 17/700) · 본문 14 · 강조 14/700 · 보조 13 · 소형 12 · 캡션 12/700 letter-spacing .04em · 배지 11/700

**Radius**: 박스 10–12 · 칩 4–6 · 데이터 박스 8 · pill = 높이/2
**Strokes**: 박스 1.5 (Pipeline 2) · 연결선 1.6 · 실패/중단 경로 1.5 dash `5 4` · 부분 성공 pill dash `4 3`
**Arrowheads**: 삼각 marker 8×8 (회색/빨강/주황 3종)
**Spacing**: 박스 간 수직 간격 ≈ 36px(화살표 길이), 박스 내부 좌측 패딩 20–28px
**Shadows**: 없음

## Assets
외부 이미지·아이콘 없음. 모든 도형은 SVG 기본 요소(rect, circle, path, text)입니다. 웹폰트는 Pretendard CDN(뷰어 HTML)만 사용하며, SVG 단독 사용 시 설치된 시스템 폰트로 대체됩니다(글자 폭이 약간 달라질 수 있음 — 필요 시 PNG로 래스터화하거나 텍스트를 아웃라인 처리).

## Files
- `defect-chatbot-architecture.svg` — 최종 다이어그램 (원본, 문서에 바로 삽입 가능)
- `Architecture Viewer.html` — 브라우저 미리보기용 래퍼 (Pretendard 로드 + 반응형 스케일)
