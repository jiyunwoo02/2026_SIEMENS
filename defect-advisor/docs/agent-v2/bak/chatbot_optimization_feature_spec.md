# 챗봇 최적화 기능 추가 명세서

> 이 문서는 Cursor에 작업을 지시하기 위한 명세서입니다.
> **작업 전에 기존 코드베이스를 먼저 읽고**, 기존 구조·네이밍·언어·프레임워크 관례를 따라 구현하세요.
> 이 문서에서 코드가 예시로 나오는 부분은 Python 기준 예시이며, 기존 프로젝트의 언어/스타일이 다르면 그에 맞춰 변환하세요.

---

## 1. 배경

제조 공정 데이터로 결함(불량) 여부를 예측하는 시스템이 있다.

- 모델: GBT 분류 모델 (Altair AI Studio에서 학습, Altair AI Hub에 배포)
- 라벨: `high_defect_flag` (`0` = 정상, `1` = 불량)
- AI Hub에 **두 개의 엔드포인트**가 존재한다.
  1. **예측 엔드포인트** (기존): 공정 조건을 입력받아 결함률을 반환
  2. **최적화 엔드포인트** (신규 연동 대상): 목표(`target`)를 입력받아 Prescriptive Analytics(진화적 최적화)로 최적 공정 조건을 반환

## 2. 현재 상태 (기존 챗봇)

1. 사용자가 자연어로 질의한다.
2. LLM이 질의에서 **공정 조건 값들을 추출**해 구조화한다.
3. 구조화된 값을 **예측 엔드포인트**로 송신한다.
4. 응답으로 받은 **결함률**을 사용자에게 보여 준다.

## 3. 목표

기존 챗봇에 **최적화 기능**을 추가한다. 최종적으로 챗봇은 **결함률 예측 결과와 최적화 결과를 모두 출력**할 수 있어야 한다.

### 3.1 범위

- 포함: 의도 분류 확장, 최적화 API 클라이언트, 결과 포맷팅, 오류 처리, 테스트
- 제외: AI Studio 프로세스 수정, 모델 재학습, AI Hub 배포 설정 변경, 기존 예측 흐름의 동작 변경

### 3.2 기존 동작 보존

- 기존 "결함률 예측" 흐름은 **동작이 바뀌지 않아야 한다.** (회귀 방지)

---

## 4. 최적화 API 명세

### 4.1 요청

| 항목 | 값 |
|---|---|
| Method | `GET` |
| URL | `{OPTIMIZATION_API_URL}` (환경변수, 아래 4.4 참고) |
| Query | `target` (필수): `"0"` 또는 `"1"` |
| 타임아웃 | 클라이언트 타임아웃은 서버 최적화 시간보다 넉넉하게 (초기값 180초, 설정 가능하게) |

호출 예시 (curl):

```bash
curl -G -s --max-time 180 "$OPTIMIZATION_API_URL" --data-urlencode "target=1"
```

### 4.2 `target`의 의미 (중요)

현재 AI Studio 프로세스는 `class name = %{target}`, `optimization direction = minimize`로 설정되어 있다.
즉 **`target`은 "확률을 최소화할 클래스"** 를 의미한다.

| target | 서버 동작 | 의미 | 결과 특징 |
|---|---|---|---|
| `1` | 불량(1) 확률 **최소화** | 불량을 줄이는 조건 탐색 | 예측 `0`(정상), `confidence(1)` ≈ 0에 가까움 |
| `0` | 정상(0) 확률 **최소화** | 불량이 발생하기 쉬운 조건 탐색 | 예측 `1`(불량), `confidence(0)` ≈ 0에 가까움 |

> 사용자 질의의 단어("불량", "정상")를 `target`에 그대로 매핑하면 **반대 결과**가 나올 수 있다.
> 반드시 **사용자의 의도**를 분류한 뒤 아래 5장의 매핑 표로 변환한다.

### 4.3 응답

HTTP 200, `Content-Type: application/json`. `data` 배열에 **최적 입력값 1행**이 들어 있다.

```json
{
  "data": [
    {
      "incoming_material_quality_score": 83.01098615566448,
      "tool_wear_pct": 12.21321075973406,
      "planned_quantity": 557.0,
      "shift": "DAY",
      "production_line": "LINE-BPR-02",
      "process_setting_deviation_pct": 2.5936167438575084,
      "ambient_humidity_pct": 71.89930496757862,
      "fixture_alignment_offset_mm": 0.4769401729445295,
      "supplier_code": "SIM-SUP-A",
      "weld_energy_setting_pct": 98.9762843050233,
      "coating_target_thickness_um": 112.39879586287252,
      "days_since_maintenance": 40.0,
      "confidence(1)": 0.017200065769509276,
      "confidence(0)": 0.9827999342304907,
      "prediction(high_defect_flag)": "0"
    }
  ]
}
```

필드 설명:

| 구분 | 필드 | 설명 |
|---|---|---|
| 최적 입력값 (11개) | `incoming_material_quality_score`, `tool_wear_pct`, `planned_quantity`, `shift`, `production_line`, `process_setting_deviation_pct`, `ambient_humidity_pct`, `fixture_alignment_offset_mm`, `supplier_code`, `weld_energy_setting_pct`, `coating_target_thickness_um`, `days_since_maintenance` | 모델이 사용하는 공정 조건. 위 12개 키가 입력 조건이다 (실제 키 목록은 기존 예측 요청 스키마와 대조해 확인할 것) |
| 결과 | `confidence(1)` | **결함(불량) 확률** |
| 결과 | `confidence(0)` | 정상 확률 |
| 결과 | `prediction(high_defect_flag)` | 예측 라벨 (`"0"` 또는 `"1"`, 문자열) |

> 키 이름에 괄호가 포함되어 있다 (`confidence(1)`). 파싱 시 문자열 키로 접근할 것.

### 4.4 설정 / 보안

- 엔드포인트 URL은 **환경변수**로 관리한다 (`OPTIMIZATION_API_URL`). 코드·저장소에 하드코딩하지 않는다.
- 인증이 필요해지는 경우를 대비해 `OPTIMIZATION_API_TOKEN`(선택)을 지원하고, 값이 있으면 `Authorization: Bearer` 헤더를 붙인다.
- 로그에 토큰이나 사용자 입력 원문 전체를 남기지 않는다.
- `.env.example`에 변수명만 추가한다 (실제 값 제외).

### 4.5 알려진 특성 (구현 시 고려)

- 진화적 최적화라서 **같은 요청도 호출마다 결과가 조금씩 다를 수 있다.**
- 응답 시간이 예측 API보다 **훨씬 길 수 있다.** 사용자에게 "최적화 중" 안내를 보여 준다.
- 최적 입력값에는 **현장에서 임의로 바꿀 수 없는 변수**(`shift`, `supplier_code`, `planned_quantity`, `ambient_humidity_pct`, `production_line` 등)가 포함될 수 있다. 현재 서버는 이 값들을 고정하지 않는다. (6.4 참고)

---

## 5. 의도 분류 및 target 매핑

### 5.1 의도(intent) 정의

LLM은 사용자 질의에서 아래 의도를 분류한다. **LLM이 `target` 숫자를 직접 고르게 하지 않는다.** 의도만 출력하고, 숫자 변환은 코드의 고정 사전으로 한다.

| intent | 설명 | 호출하는 API |
|---|---|---|
| `predict` | 주어진 공정 조건의 결함률 예측 (기존 기능) | 예측 |
| `optimize_reduce_defect` | 불량을 줄이는 조건 / 정상(양품) 비율을 높이는 조건 탐색 | 최적화 (`target=1`) |
| `optimize_find_defect_risk` | 불량이 발생하기 쉬운 조건 / 위험 조건 탐색 | 최적화 (`target=0`) |
| `predict_and_optimize` | 현재 조건의 결함률 + 개선 조건을 함께 요청 | 예측 + 최적화 (`target=1`) |
| `clarify` | 의도가 불분명 | 호출하지 않고 사용자에게 되묻기 |

### 5.2 intent → target 변환 (코드에서 고정)

```python
INTENT_TO_TARGET = {
    "optimize_reduce_defect": "1",     # 불량(1) 확률 최소화
    "predict_and_optimize": "1",       # 불량(1) 확률 최소화
    "optimize_find_defect_risk": "0",  # 정상(0) 확률 최소화 = 불량 유발 조건 탐색
}

def build_target(intent: str) -> str:
    if intent not in INTENT_TO_TARGET:
        raise ValueError(f"지원하지 않는 의도: {intent}")
    return INTENT_TO_TARGET[intent]
```

- 변환 결과는 반드시 `"0"` 또는 `"1"`인지 **재검증**한 뒤 호출한다.
- 사전에 없는 의도는 호출하지 않는다.

### 5.3 질의 예시와 기대 분류

| 사용자 질의 예시 | 기대 intent | target |
|---|---|---|
| "불량을 줄이려면 공정 조건을 어떻게 해야 해?" | `optimize_reduce_defect` | 1 |
| "정상으로 나오는 최적 조건 알려줘" | `optimize_reduce_defect` | 1 |
| "양품률을 높이는 조건이 뭐야?" | `optimize_reduce_defect` | 1 |
| "불량이 가장 많이 나는 조건은?" | `optimize_find_defect_risk` | 0 |
| "위험한 공정 조건 조합 알려줘" | `optimize_find_defect_risk` | 0 |
| "공구 마모 30%, 야간조일 때 결함률은?" | `predict` | (예측 API) |
| "지금 조건 결함률 알려주고, 더 좋게 하려면 어떻게 해?" | `predict_and_optimize` | 1 |
| "최적화해줘" | `clarify` | 호출 안 함 |
| "정상으로 해줘" | `clarify` (모호) | 호출 안 함 |

> "정상"이라는 단어가 나와도 의도가 "정상 비율을 높이고 싶다"이면 `target=1`이다. 단어가 아니라 **방향**으로 판단한다.

### 5.4 구조화 출력 스키마 (LLM)

기존 공정 조건 추출 스키마에 의도 필드를 **추가**한다. (기존 필드는 변경하지 않는다)

```json
{
  "intent": "optimize_reduce_defect",
  "conditions": {
    "tool_wear_pct": 30.0,
    "shift": "NIGHT"
  },
  "missing_fields": []
}
```

- `conditions`는 기존 추출 로직의 출력 형식을 그대로 따른다.
- `intent`는 5.1의 enum 중 하나여야 한다. enum 외 값은 `clarify`로 처리한다.
- 최적화 전용 의도에서는 `conditions`가 비어 있어도 된다 (최적화 API는 공정 조건을 입력받지 않음).
- `predict`, `predict_and_optimize`는 예측에 필요한 조건이 부족하면 기존 방식대로 부족한 값을 되묻는다.

---

## 6. 구현 요구사항

### 6.1 최적화 API 클라이언트

- 단일 함수/클래스로 분리 (예: `optimization_client`). 기존 예측 클라이언트가 있으면 같은 패턴을 따른다.
- 입력: `target: str` ("0"/"1")
- 요청 시 쿼리 파라미터는 라이브러리의 params 인자를 사용해 **자동 URL 인코딩**되게 한다. (문자열 직접 결합 금지)
- 출력: 파싱된 결과 객체 (최적 조건 dict, `defect_probability`, `normal_probability`, `predicted_label`)
- `data`가 비어 있거나 키가 없으면 오류 처리

예시:

```python
def parse_optimization_response(payload: dict) -> dict:
    rows = payload.get("data") or []
    if not rows:
        raise ValueError("최적화 결과가 비어 있습니다.")
    row = rows[0]
    return {
        "conditions": {k: v for k, v in row.items()
                       if not k.startswith(("confidence(", "prediction("))},
        "defect_probability": row["confidence(1)"],
        "normal_probability": row["confidence(0)"],
        "predicted_label": row["prediction(high_defect_flag)"],
    }
```

### 6.2 오케스트레이션 흐름

```
사용자 질의
   │
   ▼
LLM: intent + conditions 추출
   │
   ├─ predict ───────────────► 예측 API ─► 결함률 출력 (기존 동작)
   │
   ├─ optimize_* ────────────► build_target ─► 최적화 API ─► 최적화 결과 출력
   │
   ├─ predict_and_optimize ──► 예측 API + 최적화 API(target=1) ─► 비교 출력
   │
   └─ clarify ───────────────► 되묻기 (API 호출 없음)
```

- `predict_and_optimize`에서 두 호출은 독립적이므로 동시 호출(병렬)해도 되지만, 한쪽이 실패해도 나머지 결과는 보여 준다 (부분 성공 허용).

### 6.3 결과 출력 형식

**공통 원칙**
- 의도에 맞는 문구를 쓴다.
  - `target=1`: "불량 확률을 낮추는 조건"
  - `target=0`: "불량이 발생하기 쉬운 조건"
- 결함 확률은 `confidence(1)`을 퍼센트로 표기한다 (소수점 1~2자리).
- 최적화 결과는 **모델 기반 추정**이며 실제 공정 결과를 보장하지 않음을 한 줄로 안내한다.

**예시 출력 (`predict_and_optimize`)**

```
현재 입력 조건의 예상 결함률은 12.4%입니다.

결함률을 낮추는 최적 조건은 아래와 같습니다. (예상 결함률 1.7%)

| 항목 | 현재 | 최적 |
|---|---|---|
| 공구 마모율(%) | 30.0 | 12.2 |
| 입고 자재 품질 점수 | 78.5 | 83.0 |
| ... | ... | ... |

※ 이 결과는 모델 기반 추정이며 실제 결과를 보장하지 않습니다.
```

- 현재 조건과 비교할 수 있을 때(`predict_and_optimize`)는 **현재 vs 최적** 표로 보여 주고, 변경폭이 큰 항목을 강조한다.
- 최적화만 요청한 경우에는 최적 조건 표와 예상 결함률만 보여 준다.
- 한 행의 11개 이상 항목은 표로 출력한다. 항목 이름은 한글 라벨로 매핑한다 (매핑 사전은 한 곳에 정의).

### 6.4 조절 불가 변수 처리 (1차 범위)

- 1차 구현에서는 서버 응답의 **모든 항목을 그대로 표시**한다.
- 단, `shift`, `supplier_code`, `planned_quantity`, `ambient_humidity_pct`, `production_line`은 현장에서 바꾸기 어려울 수 있으므로 **"참고값"** 같은 보조 표기를 달 수 있게 라벨 사전에 플래그(`controllable: bool`)를 둔다. 기본값은 `true`로 두고, 어떤 변수를 `false`로 할지는 설정 파일에서 관리한다.
- 서버 측에서 고정하는 방식은 별도 작업이며 이번 범위가 아니다.

### 6.5 오류 처리

| 상황 | 처리 |
|---|---|
| 타임아웃 | "최적화 계산이 오래 걸리고 있어요. 잠시 후 다시 시도해 주세요." (재시도 1회 허용, 설정 가능) |
| HTTP 4xx | 호출 파라미터/인증 오류로 간주, 사용자에게는 일반 메시지, 로그에는 상태 코드 기록 |
| HTTP 5xx | 서버 오류 안내, 재시도 1회 |
| 응답 JSON 파싱 실패 / `data` 비어 있음 | 오류 처리, 부분 결과 노출 금지 |
| intent가 enum 밖 / `clarify` | API 호출 없이 되묻기 |
| `target`이 `"0"`/`"1"`이 아님 | 호출하지 않고 내부 오류로 처리 (LLM 출력을 URL에 그대로 넣지 않는다) |

- 사용자에게 스택트레이스나 내부 URL을 노출하지 않는다.
- 사용자에게 로딩 상태를 보여 준다 (최적화 호출은 수 초 이상 걸릴 수 있음).

### 6.6 로깅

- 호출 시 `intent`, `target`, 소요 시간, 상태 코드를 기록한다.
- 원문 질의 전체나 토큰은 기록하지 않는다.

---

## 7. 테스트

### 7.1 단위 테스트

- `build_target`: 각 intent → 기대 target, 미정의 intent → 예외
- `parse_optimization_response`: 정상 응답, 빈 `data`, 키 누락
- 의도 분류 결과(enum 외 값 포함) 처리

### 7.2 통합/모킹 테스트

- 최적화 API를 **모킹**해서 `predict_and_optimize`의 부분 실패(예측만 성공 / 최적화만 성공) 동작 확인
- 요청에 `target` 쿼리 파라미터가 올바르게 붙는지 확인 (`?target=1`, `?target=0`)

### 7.3 수동 검증 (실제 엔드포인트, 개발 환경에서만)

1. `target=1`과 `target=0`으로 각각 호출해 결과가 **서로 다른지** 확인한다. (기본값 `1`이 고정되어 있어 같은 값만 호출하면 매크로 반영 여부를 알 수 없다)
2. 같은 `target`을 두세 번 호출해 결과 변동 폭을 확인한다.
3. 응답 시간을 측정해 타임아웃 기본값이 적절한지 확인한다.

---

## 8. 완료 기준 (Acceptance Criteria)

- [ ] 기존 `predict` 흐름이 이전과 동일하게 동작한다.
- [ ] "불량을 줄이는 조건" 류의 질의가 `target=1`로 호출된다.
- [ ] "불량이 잘 나는 조건" 류의 질의가 `target=0`으로 호출된다.
- [ ] 의도가 모호한 질의는 API 호출 없이 되묻는다.
- [ ] `predict_and_optimize`에서 현재 결함률과 최적 조건이 함께 출력된다.
- [ ] 한쪽 API가 실패해도 나머지 결과는 출력된다.
- [ ] 타임아웃·4xx·5xx·빈 응답에서 사용자에게 안전한 메시지가 나온다.
- [ ] 엔드포인트 URL과 토큰이 코드에 하드코딩되어 있지 않다.
- [ ] 단위 테스트와 모킹 통합 테스트가 통과한다.

---

## 9. 열린 질문 (구현 전에 확인할 것)

Cursor는 코드베이스에서 확인 가능한 항목은 직접 확인하고, 확인이 안 되는 항목은 구현 전에 사용자에게 질문한다.

1. 기존 예측 엔드포인트의 요청/응답 스키마와 호출 방식은? (코드에서 확인)
2. 기존 챗봇의 언어·프레임워크·LLM 호출 방식(구조화 출력, 함수 호출, 프롬프트 방식)은? (코드에서 확인)
3. 기존 공정 조건 추출 스키마의 필드 이름이 응답의 입력 키 목록(4.3)과 일치하는가? 한글 라벨은 어디에 정의되어 있는가?
4. 최적화 결과를 사용자에게 보여줄 때 **조절 불가 변수**를 숨길지, 참고값으로 표시할지?
5. 최적화 API에 인증이 필요한가? (현재 테스트에서는 인증 없이 호출됨)
6. `predict`와 `optimize`를 항상 같이 보여 줄지, 의도에 따라 분기할지 (이 명세는 의도 기반 분기를 기본으로 함)
7. 최적화 API의 정상 응답 시간(수 초? 수십 초?)은 얼마인가? 타임아웃과 로딩 UI에 영향.
