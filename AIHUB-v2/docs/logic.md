# AIHUB-v2 챗봇 로직 문서

## 1. 개요

AIHUB-v2는 한국어 자연어 질의로 제조 공정의 **결함률 예측** 및 **공정 최적화**를 수행하는 챗봇입니다.
사용자 발화에서 공정 조건 12개를 추출하고, 의도(intent)에 따라 외부 ML 예측 API 또는 최적화 API를 호출합니다.

---

## 2. 전체 처리 흐름

```
사용자 질의 (자연어)
    │
    ▼
[1단계] LLM 추출 (QueryExtractor.extract)
    - intent 분류 (6종 중 하나)
    - 공정 조건 12개 필드 JSON 추출
    - 모호한 값 → null + ambiguous_fields 기록
    │
    ▼
[2단계] intent 분기 (DefectRatePipeline.run)
    │
    ├─ predict                 → [3a] 예측 흐름
    ├─ predict_and_optimize    → [3b] 예측 후 최적화 (target="1", 개선 방향)
    ├─ predict_and_find_risk   → [3b] 예측 후 최적화 (target="0", 위험 방향)
    ├─ optimize_reduce_defect  → [3c] 최적화만 (target="1")
    ├─ optimize_find_defect_risk → [3c] 최적화만 (target="0")
    └─ clarify                 → [3d] 고정 문구 반환 (API 호출 없음)
    │
    ▼
[4단계] 결과 포맷 → PipelineResult 반환
```

---

## 3. 각 단계 상세

### 3.1 LLM 추출 단계 (`llm.py`, `pipeline.py:QueryExtractor`)

- `SDCLLMClient.chat_json()`으로 LLM에 동기 HTTP 요청을 보냅니다.
- 시스템 프롬프트(`EXTRACTION_SYSTEM_PROMPT`)에 12개 필드 명세와 intent 분류 규칙이 포함됩니다.
- LLM은 다음 JSON을 반환합니다:

  ```json
  {
    "intent": "predict",
    "records": [{ "production_line": "LINE-BPR-01", "shift": "DAY", ... }],
    "ambiguous_fields": [],
    "notes": null
  }
  ```

- `intent`가 `INTENTS` 목록에 없거나 누락된 경우 `"clarify"`로 처리합니다.
- **LLM은 intent 이름만 선택합니다.** 최적화 API의 `target` 값("0"/"1") 변환은 코드(`build_target()`)가 담당합니다 (환각 방지).

#### JSON 출력 모드 폴백 (auto 모드)

LLM 서버의 구조화 출력 지원 여부에 따라 아래 순서로 자동 시도합니다:

1. `json_schema` (strict JSON Schema)
2. `json_object` (스키마는 프롬프트로 전달)
3. `prompt` (response_format 없이 프롬프트로만 유도)

성공한 모드를 이후 호출에 고정하므로 폴백은 최초 1회만 발생합니다.

---

### 3.2 슬롯 필링 세션 (`pipeline.py:SlotFillingSession`)

멀티턴 대화를 지원하기 위해 세션에 공정 조건 값을 누적 저장합니다.

- `merge()`: 이번 발화의 추출값을 기존 슬롯에 병합합니다. `null`은 "이번에 언급 안 함"을 의미하며 기존 값을 유지합니다.
- `known()`: 현재 세션에서 확인된 값(non-null)만 반환합니다.
- `missing()`: 아직 값이 없는 필드를 `ALL_FIELDS` 순서대로 반환합니다.
- `track_missing()`: 같은 누락 목록이 연속으로 나타난 횟수를 기록합니다 (반복 재질문 감지).
- `reset()`: 세션 슬롯·턴 수·재질문 이력을 초기화합니다 (session_id는 유지).

---

### 3.3 공통 조건 수집·예측 단계 (`pipeline.py:_gather_and_predict`)

`predict`, `predict_and_optimize`, `predict_and_find_risk` 세 경로가 공유하는 공통 단계입니다.

```
추출 레코드가 없고 세션도 비어 있음?
    → need_more_info (12개 필드 전부 재질문)

모호 필드(ambiguous_fields) 처리
    → 해당 필드를 세션 슬롯에서 제거 (기존 확인값도 null로 리셋)

즉시 검증 (validate_provided_fields)
    → 허용값 밖 코드/범위 밖 수치 → invalid_input 반환

슬롯 병합 (session.merge)
    → missing 필드가 남아 있음?
        → need_more_info (누락 필드 재질문)

Pydantic 검증 (DefectRateInput)
    → 최종 범위·타입 검사

ML 예측 API 호출 (DefectRateMLClient.predict)
    → 실패 시 endpoint_error 반환

→ 성공 시 (None, {"records": ..., "out": ...}) 반환
```

---

### 3.4 intent별 실행 경로

#### [3a] `predict` — 결함률 예측

```
_gather_and_predict()          ← ML 예측 API 동기 호출
    │
    └─ explain=True 이면
           LLM 해설 호출 (self._explain)   ← LLM 동기 호출
       explain=False 이면
           "예측 결함률: X.XX%" 문자열 직접 생성
```

- ML API와 LLM 해설이 **순차 실행**됩니다.
- 전체 지연 = ML API latency + (explain=True이면) LLM latency

#### [3b] `predict_and_optimize` / `predict_and_find_risk` — 예측 + 최적화

```
_gather_and_predict()          ← ML 예측 API 동기 호출 (조건 부족 시 early return)
    │
    ▼
build_target(intent)
    predict_and_optimize   → target="1"  (불량 확률 최소화)
    predict_and_find_risk  → target="0"  (정상 확률 최소화 = 위험 조건 탐색)
    │
    ▼
OptimizationClient().optimize(target)   ← 최적화 API 동기 호출
    │
    ├─ 성공: optimization_result 저장
    └─ 실패: optimization_error 저장 (예측 결과는 그대로 반환 — 부분 성공)
    │
    ▼
_format_predict_and_optimize()   ← LLM 호출 없음, 코드 기반 포맷
```

**핵심**: 예측 → 최적화가 **완전히 순차(동기)** 실행됩니다. `asyncio`/`await`는 미사용이며, `httpx.Client`(동기) 기반입니다.

- 전체 지연 = ML API latency + 최적화 API latency
- 최적화 실패 시에도 예측 결과는 포함하여 반환합니다 (부분 성공 허용).
- **해설 LLM을 추가로 호출하지 않습니다.** `predict`와 달리 코드 포매터가 직접 answer를 구성합니다.

#### [3c] `optimize_reduce_defect` / `optimize_find_defect_risk` — 최적화만

```
build_target(intent)
    optimize_reduce_defect      → target="1"
    optimize_find_defect_risk   → target="0"
    │
    ▼
OptimizationClient().optimize(target)   ← 최적화 API 동기 호출
    │
    ▼
_format_optimize_only()   ← 코드 기반 포맷
```

- 사용자가 공정 조건을 입력하지 않아도 동작합니다.
- ML 예측 API와 LLM 해설을 호출하지 않습니다.

#### [3d] `clarify` — 의도 불명확

- 어떤 외부 API도 호출하지 않습니다.
- 최적화 방향(개선/위험)을 되묻는 고정 문구를 즉시 반환합니다.

---

## 4. intent → target 매핑

최적화 API의 `target` 파라미터 변환은 LLM이 아닌 코드(`optimization.py:build_target`)가 담당합니다.

| intent | target | 의미 |
|---|---|---|
| `optimize_reduce_defect` | `"1"` | 불량(high_defect_flag=1) 확률 최소화 조건 |
| `predict_and_optimize` | `"1"` | 불량 확률 최소화 조건 |
| `optimize_find_defect_risk` | `"0"` | 정상(=0) 확률 최소화 = 불량 유발 조건 탐색 |
| `predict_and_find_risk` | `"0"` | 불량 유발 조건 탐색 |

> **주의**: 이 매핑이 틀리면 최적화 기능의 방향이 반대로 뒤집힙니다. 현재 자동화 테스트가 없으므로 운영 API로 교차 검증을 권장합니다.

---

## 5. 최적화 API 통신 (`optimization.py:OptimizationClient`)

```
GET {OPTIMIZATION_API_URL}?target=<0|1>
Accept: application/json
Authorization: Bearer <token>   (토큰 설정 시)
```

응답 형식 (`data[0]`):
```json
{
  "data": [{
    "production_line": "LINE-BPR-01",
    "shift": "DAY",
    ... (조건 12개),
    "confidence(1)": 0.12,
    "confidence(0)": 0.88,
    "prediction(high_defect_flag)": "0"
  }]
}
```

- `4xx` 오류: 즉시 실패 (재시도 없음)
- `5xx` / 타임아웃 / 네트워크 오류: 설정된 횟수만큼 재시도

---

## 6. ML 예측 API 통신 (`ml.py:DefectRateMLClient`)

```
POST {AI_HUB_ENDPOINT_URL}
Content-Type: application/json

{"data": [{12개 조건 필드}, ...]}
```

- 재시도: 타임아웃·`5xx`에만 재시도, `4xx`는 즉시 실패
- 지수 백오프: 0.5초 → 1초 → 2초
- `MOCK_ML=true` 설정 시 더미 값(1.65%, 2.65%, ...)을 반환합니다.

---

## 7. 응답 구조 (`PipelineResult`)

| 필드 | 설명 |
|---|---|
| `status` | `ok` / `need_more_info` / `invalid_input` / `endpoint_error` / `llm_error` / `clarify` |
| `answer` | 사용자에게 보여줄 Markdown 텍스트 |
| `intent` | 이번 발화의 분류된 의도 |
| `predictions` | 레코드별 예측 결함률(%) 목록 |
| `optimization` | 최적화 API 파싱 결과 (`null`이면 호출 안 했거나 실패). `optimization["latency_ms"]`에 최적화 API 응답 시간 포함 |
| `missing_fields` | 아직 값이 없는 필드 목록 |
| `ambiguous_fields` | 모호 표현으로 null 처리된 필드(`missing_fields`의 부분 집합) |
| `invalid_fields` | 범위·허용값 검증에 실패한 필드(`invalid_input` 상태일 때) |
| `known_slots` | 세션에 확인된 현재 슬롯 값 |
| `errors` | 부분 실패 메시지 목록 |
| `latency_ms` | ML API 호출 소요 시간(최적화 API 시간은 `optimization["latency_ms"]`에 별도 포함) |
| `unit` | 예측값 단위, 항상 `"percent"` |
| `model_input` | ML API에 전달한 원본 페이로드(`data` 배열) |

> HTTP 상태 코드와 무관하게 처리 결과는 항상 HTTP 200으로 반환됩니다. `status` 필드로 성공 여부를 판단해야 합니다.

---

## 8. LLM 호출 횟수 요약

| intent | LLM 추출 | ML 예측 API | 최적화 API | LLM 해설 |
|---|:---:|:---:|:---:|:---:|
| `predict` (explain=true) | 1회 | 1회 | - | 1회 |
| `predict` (explain=false) | 1회 | 1회 | - | - |
| `predict_and_optimize` | 1회 | 1회 | 1회 | - |
| `predict_and_find_risk` | 1회 | 1회 | 1회 | - |
| `optimize_reduce_defect` | 1회 | - | 1회 | - |
| `optimize_find_defect_risk` | 1회 | - | 1회 | - |
| `clarify` | 1회 | - | - | - |

- 모든 외부 호출은 **동기·순차**로 실행됩니다 (`asyncio` 미사용).
- `predict_and_*` 경로: ML 예측 API → 최적화 API 순서로 호출되며, LLM 해설은 없습니다.

---

## 9. 세션 관리

- 세션은 서버 프로세스 메모리에만 저장됩니다 (재시작 시 소멸).
- HTTP API: `session_id`를 요청마다 전달하면 멀티턴 대화를 유지합니다.
- CLI: 대화형 모드에서 단일 세션을 프로세스 종료까지 유지합니다.
- `DELETE /chat/session/{session_id}`로 특정 세션을 명시적으로 삭제할 수 있습니다.
- 최적화 전용 의도(`optimize_*`)는 세션 슬롯과 무관하게 동작합니다.

---

## 변경 이력

- (작성일 미상) 최초 작성: AIHUB-v2 처리 흐름·intent 분기·슬롯 필링 등 동작 로직 정리.
- **2026-11-02**: 소스 대조 후 `PipelineResult` 필드 표에 누락 항목 3개 추가 — `invalid_fields`(검증 실패 필드), `unit`(항상 "percent"), `model_input`(ML 페이로드). `optimization`·`latency_ms` 설명을 소스 기준으로 보완했다.
