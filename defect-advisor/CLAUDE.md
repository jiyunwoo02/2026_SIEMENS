# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 실행 명령

### 환경 준비

```bash
# defect-advisor/ 디렉터리에서 실행해야 함 (.env 로딩 기준이 cwd)
cd defect-advisor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`.env` 파일을 직접 작성해야 함 (Git 제외):
```dotenv
api_key=<SDC LLM 인증 키>
LLM_MODEL=<모델 이름>
AI_HUB_ENDPOINT_URL=<결함률 예측 API 주소>
OPTIMIZATION_API_URL=<최적화 API 주소>   # 최적화 기능 사용 시 필요
MOCK_ML=true                              # ML API 없이 테스트할 때
```

### 실행

```bash
# 대화형 CLI
python -m aihub

# 단발 질의 (JSON 출력)
python -m aihub "LINE-BPR-01 주간조 불량률 예측해줘" --json

# 웹 UI + HTTP API 서버 (http://127.0.0.1:8000)
bash aihub/web/ui.sh
bash aihub/web/ui.sh 9000            # 포트 변경
HOST=0.0.0.0 bash aihub/web/ui.sh   # 외부 접속 허용
```

### 테스트 (자동화 없음, 수동 스모크 테스트만 존재)

```bash
# 최적화 API를 curl로 직접 호출 (out_0.json / out_1.json 저장)
bash test/curl_test_classification.sh

# HTTP API 스모크 테스트 (서버 먼저 실행 필요)
bash test/web_smoke_test.sh

# CLI 스모크 테스트
bash test/cli_smoke_test.sh
```

pytest는 미사용. `test/__pycache__/`에 과거 `.pyc`만 남아 있고 `.py` 원본 없음.

---

## 문서 작업 규칙

- **변경 이력 필수**: 문서(`*.md`)를 수정할 때는 반드시 해당 문서 **하단**에 `## 변경 이력` 섹션을 두고, 날짜·변경 내용을 한 줄로 기록한다.
  ```
  ## 변경 이력
  - **2026-11-02**: 설명 추가 — XXX 내용을 YYY로 수정했다.
  ```
- `[수정]`/`[신규]`/`[확인 필요]` 같은 인라인 주석을 문서 본문에 남기지 않는다. 변경 경위는 변경 이력 섹션에만 기록한다.
- 소스 코드를 직접 확인하기 전에는 "추정", "확인 필요" 등의 표현을 명시한다. 확인 후 해당 표현을 제거한다.

---

## 아키텍처

### 처리 흐름 (모두 동기·순차, asyncio 미사용)

```
사용자 질의
  → QueryExtractor.extract()   — LLM 동기 호출, intent + 12개 필드 JSON 추출
  → DefectRatePipeline.run()   — intent 분기
       predict                 → _gather_and_predict() + LLM 해설(선택)
       predict_and_optimize    → _gather_and_predict() → OptimizationClient(target="1")
       predict_and_find_risk   → _gather_and_predict() → OptimizationClient(target="0")
       optimize_reduce_defect  → OptimizationClient(target="1") 만
       optimize_find_defect_risk → OptimizationClient(target="0") 만
       clarify                 → 고정 문구 반환, API 호출 없음
  → PipelineResult 반환
```

### intent → API 분기 상세

| intent | `_run_*` 메서드 | ML 예측 API | 최적화 API | LLM 해설 | `target` |
|---|---|---|---|---|---|
| `predict` | `_run_predict` | ✓ | — | ✓(선택) | — |
| `predict_and_optimize` | `_run_predict_and_optimize` | ✓ | ✓ | — | `"1"` |
| `predict_and_find_risk` | `_run_predict_and_optimize` | ✓ | ✓ | — | `"0"` |
| `optimize_reduce_defect` | `_run_optimize_only` | — | ✓ | — | `"1"` |
| `optimize_find_defect_risk` | `_run_optimize_only` | — | ✓ | — | `"0"` |
| `clarify` | `_run_clarify` | — | — | — | — |

- `target="1"`: 불량(high_defect_flag=1) 확률 최소화 조건 탐색
- `target="0"`: 정상(=0) 확률 최소화 = 불량 유발 조건 탐색
- `predict_and_*`: 최적화 실패 시에도 `status="ok"` 반환(부분 성공). `optimization=null` + `errors` 필드로 실패 여부 확인.

### PipelineResult 주요 필드

| 필드 | 타입 | 설명 |
|---|---|---|
| `status` | str | `ok` / `need_more_info` / `invalid_input` / `endpoint_error` / `llm_error` / `clarify` |
| `answer` | str | 사용자에게 보여줄 Markdown 텍스트 |
| `intent` | str | 이번 발화의 분류된 의도 (기본값 `"predict"`) |
| `predictions` | list | 레코드별 예측 결함률(%) |
| `optimization` | dict\|None | 최적화 API 파싱 결과. 호출 안 했거나 실패 시 `null` |
| `errors` | list | 부분 실패 메시지 목록 |
| `missing_fields` | list | 아직 값이 없는 필드 |
| `ambiguous_fields` | list | 모호 표현으로 null 처리된 필드 |
| `known_slots` | dict | 세션에 확인된 현재 슬롯 값 |
| `latency_ms` | float | ML API 호출 소요 시간 |

### 핵심 모듈과 역할

| 파일 | 역할 |
|---|---|
| `pipeline.py` | 오케스트레이션 중심. `_gather_and_predict()`가 predict·predict_and_\* 3종 경로의 공통 단계(슬롯 병합 → 검증 → ML 호출)를 담당 |
| `schema.py` | 12개 필드 정의(`ALL_FIELDS`, `FIELD_SPEC`), `INTENTS` 목록, `DefectRateInput` Pydantic 모델, 허용값 화이트리스트 |
| `llm.py` | `SDCLLMClient` (Siemens SDC 게이트웨이), `EXTRACTION_SYSTEM_PROMPT`, JSON 출력 폴백 로직(`json_schema → json_object → prompt`) |
| `ml.py` | `DefectRateMLClient` — POST 예측 API, 재시도·에코 검증 |
| `optimization.py` | `OptimizationClient` — GET 최적화 API, `INTENT_TO_TARGET` 매핑, `build_target()` |
| `config.py` | `Settings` (pydantic-settings), `lru_cache`로 프로세스 내 단일 인스턴스 |
| `api.py` | FastAPI — `/health`, `POST /chat/predict`, `DELETE /chat/session/{id}`, 웹 UI 정적 서빙 |
| `cli.py` | `argparse` 기반 CLI, 대화형·단발 모드 |

### 중요한 설계 결정

**intent → target 변환은 코드가 처리한다.**
`optimization.py:INTENT_TO_TARGET`과 `build_target()`이 LLM이 선택한 intent 문자열을 최적화 API의 `target`("0"/"1")으로 변환한다. LLM이 직접 target 값을 고르지 않는다(환각 방지). 이 매핑이 틀리면 최적화 방향이 반대로 뒤집히며 자동 테스트가 없으므로 변경 시 주의.

**`predict_and_*` 경로는 LLM 해설을 호출하지 않는다.**
`predict` 경로는 ML 예측 후 `_explain()`으로 LLM을 추가 호출한다. 반면 `predict_and_optimize`/`predict_and_find_risk`는 `_format_predict_and_optimize()`(코드 포매터)가 직접 answer를 구성한다.

**`predict_and_find_risk`는 명세서에 없는 추가 의도다.**
"예측 + 위험 조건 탐색"을 표현할 enum이 없어 추가됨. `target="0"` (정상 확률 최소화 = 불량 유발 조건). 관련 파일: `schema.INTENTS`, `optimization.INTENT_TO_TARGET`, `pipeline._run_predict_and_optimize`, `llm.EXTRACTION_SYSTEM_PROMPT`.

**모호한 값은 null로만 처리한다.**
LLM 추출 단계에서 값을 하나로 확정할 수 없으면 `null` + `ambiguous_fields` 기록. 코드 레벨에서 추정·보완하지 않는다. `ambiguous_fields`에 포함된 필드는 `_gather_and_predict()`에서 세션 슬롯을 비워 기존 확인값도 리셋한다.

**`.env`는 반드시 `defect-advisor/` 디렉터리에서 실행해야 로드된다.**
`config.py:Settings`가 `env_file=".env"`(상대경로)로 설정됨. `get_settings()`는 `lru_cache`로 프로세스 내 고정되므로 변경 후 재시작 필요.

**최적화 API 주소가 없어도 서버는 기동된다.**
`config.validate_runtime()`이 `optimization_api_url`을 필수로 검사하지 않는다. 최적화 의도를 실제로 요청한 시점에야 `OptimizationEndpointError`가 발생한다.

**응답 HTTP 상태는 항상 200이다.**
`status` 필드(`ok`/`need_more_info`/`invalid_input`/`endpoint_error`/`llm_error`/`clarify`)로 처리 결과를 구분해야 한다.

### 세션 관리

세션은 서버 메모리(`_sessions: dict`)에만 저장. 재시작하면 사라진다.
`SlotFillingSession.merge()`가 멀티턴 슬롯 누적을 담당. 이번 발화에서 `null`인 필드는 기존 값을 유지한다.

---

## 사용자 질의 예시

아래는 intent별 대표 질의와 동작 흐름이다. 작업 중 기능 범위를 가늠하는 데 활용한다.

### predict — 결함률 예측

```
"LINE-BPR-01 주간조, SIM-SUP-B 자재, 공구마모 45%, 실린더압 71bar로 불량률 예측해줘"
```
→ LLM이 12개 필드를 추출 → 누락 필드가 있으면 `need_more_info` → 모두 채워지면 ML API 호출 → LLM 해설 포함 답변 반환.

### predict_and_optimize — 예측 + 개선 조건

```
"현재 조건(LINE-BPR-01, 주간조, ...) 예측하고 불량 줄이는 조건도 알려줘"
```
→ ML 예측 API → 최적화 API(`target="1"`) → LLM 해설 없이 코드 포매터로 Markdown 표 생성.

### predict_and_find_risk — 예측 + 위험 조건 탐색

```
"예측하고, 불량이 더 심해지는 위험 조건도 알려줘"
```
→ ML 예측 API → 최적화 API(`target="0"`) → 코드 포매터 답변. `predict_and_optimize`와 동일 경로이며 `target`만 다르다.

### optimize_reduce_defect — 최적화만 (개선)

```
"불량률 줄이는 최적 공정 조건 알려줘"
```
→ 공정 조건 입력 없이도 동작. 최적화 API(`target="1"`)만 호출.

### optimize_find_defect_risk — 최적화만 (위험)

```
"불량이 잘 나는 위험 조건이 뭐야?"
```
→ 최적화 API(`target="0"`)만 호출.

### clarify — 의도 불명확

```
"최적화해줘" (방향 불명확)
```
→ 어떤 API도 호출하지 않고, 개선/위험 방향을 되묻는 고정 문구 반환. `status="clarify"`.

---

## 유의사항

작업 시 반드시 염두에 둬야 할 사항.

### INTENT_TO_TARGET 매핑 — 자동 테스트 없음

`optimization.py:INTENT_TO_TARGET` 사전이 틀리면 최적화 방향이 반대로 뒤집힌다. 이 매핑을 수정할 때는 실제 운영 API로 `target=0`/`target=1` 응답을 비교해 교차 검증한다. 현재 값:
```python
INTENT_TO_TARGET = {
    "optimize_reduce_defect":   "1",
    "predict_and_optimize":     "1",
    "optimize_find_defect_risk":"0",
    "predict_and_find_risk":    "0",
}
```

### 알려진 불일치 — `_format_optimize_only` 문구

`pipeline.py:_format_optimize_only()`에 "참고값으로 표시된 항목은..." 문구가 남아 있지만, `_format_conditions_table()`은 이미 2열(항목/값)만 생성하며 참고값 표시가 없다. 이 함수를 수정할 때 해당 문구도 함께 제거한다.

### 부분 성공 패턴

`predict_and_optimize`/`predict_and_find_risk` 경로는 최적화 API 실패 시에도 `status="ok"`를 반환한다. 응답을 파싱할 때 `optimization` 필드가 `null`이고 `errors`에 메시지가 있는 경우를 별도로 처리해야 한다.

### 웹 UI 제약

`aihub/web/`에는 최적화 조건 전용 렌더링 영역이 없다. 최적화 결과는 `answer` Markdown 텍스트와 `raw` JSON에서만 확인할 수 있다. 웹 UI 기능을 추가할 때 이 점을 감안해 설계한다.

---

## 변경 이력

- **2026-11-02**: 초기 작성 내용에 다음 섹션 추가. (1) 문서 작업 규칙(변경 이력 필수). (2) intent → API 분기 상세 표 및 PipelineResult 필드 표. (3) 사용자 질의 예시(intent별 6종). (4) 유의사항(INTENT_TO_TARGET, 알려진 불일치, 부분 성공 패턴, 웹 UI 제약).
