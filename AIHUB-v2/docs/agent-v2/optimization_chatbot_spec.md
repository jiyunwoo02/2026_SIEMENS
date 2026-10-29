# 공정 최적화 챗봇 개발 명세서 (독립 프로젝트)

> 이 문서는 Cursor에 작업을 지시하기 위한 명세서입니다.
> **작업 전에 프로젝트 폴더를 먼저 확인하세요.** 특히 아래 두 가지는 이미 준비되어 있습니다.
>
> - `.env`: 최적화 API 주소가 들어 있음 (변수명은 파일을 열어 확인할 것)
> - `test/curl_test_classification.sh`: 최적화 API를 curl로 호출하는 방법이 정리되어 있음 (호출 방식의 기준으로 삼을 것)
>
> 이 문서의 코드는 Python 기준 예시입니다. 언어/프레임워크가 확정되지 않았다면 11장의 열린 질문을 먼저 확인하세요.

---

## 1. 배경

제조 공정 데이터로 결함(불량) 여부를 예측하는 분류 모델이 있다.

- 모델: GBT 분류 모델 (Altair AI Studio에서 학습, Altair AI Hub에 배포)
- 라벨: `high_defect_flag` (`0` = 정상, `1` = 불량)
- AI Hub에 **최적화 엔드포인트**가 배포되어 있다. 이 엔드포인트는 목표(`target`)를 받아 Prescriptive Analytics(진화적 최적화)로 **최적 공정 조건**을 반환한다.

## 2. 목표

사용자가 자연어로 질문하면 챗봇이 **의도를 파악해 최적화 API를 호출하고, 결과(최적 공정 조건 + 예상 결함 확률)를 알기 쉽게 설명**하는 **독립 챗봇**을 만든다.

- 기존 챗봇과 **무관한 별도 프로젝트**다. 기존 코드에 병합하지 않는다.
- 이 챗봇은 **최적화 결과 제공**이 핵심 기능이다.

### 2.1 범위

- 포함: 사용자 질의의 의도 분류, 최적화 API 클라이언트, 결과 포맷팅, 오류 처리, 테스트
- 제외: AI Studio 프로세스 수정, 모델 재학습, AI Hub 배포 설정 변경, 임의 공정 조건에 대한 결함률 예측(별도 예측 엔드포인트가 필요하며 이번 범위가 아님)

---

## 3. 사용자 시나리오

1. 사용자가 "불량을 줄이려면 공정 조건을 어떻게 해야 해?"처럼 질문한다.
2. LLM이 질의의 **의도**를 분류한다.
3. 코드가 의도를 `target` 값(`0`/`1`)으로 변환한다.
4. 최적화 API를 `target` 쿼리 파라미터와 함께 호출한다.
5. 응답(최적 조건, 결함 확률)을 사용자에게 설명한다.

의도가 불분명하면 API를 호출하지 않고 사용자에게 되묻는다.

---

## 4. 최적화 API 명세

### 4.1 요청

| 항목 | 값 |
|---|---|
| Method | `GET` |
| URL | `.env`에 저장된 최적화 API 주소 (변수명은 `.env`에서 확인) |
| Query | `target` (필수): `"0"` 또는 `"1"` |
| 타임아웃 | 서버 최적화 시간보다 넉넉하게. 초기값 180초, 설정 가능하게 |

호출 방식은 `test/curl_test_classification.sh`의 방식을 따른다. 요청 파라미터는 curl의 `--data-urlencode`에 대응하도록 **HTTP 라이브러리의 params 인자**로 전달한다 (문자열 직접 결합 금지).

참고용 curl 형태:

```bash
curl -G -s --max-time 180 "$API_URL" --data-urlencode "target=1"
```

### 4.2 `target`의 의미 (중요)

현재 AI Studio 프로세스는 `class name = %{target}`, `optimization direction = minimize`로 설정되어 있다.
즉 **`target`은 "확률을 최소화할 클래스"** 를 의미한다.

| target | 서버 동작 | 의미 | 결과 특징 |
|---|---|---|---|
| `1` | 불량(1) 확률 **최소화** | 불량을 줄이는 조건 탐색 | 예측 `0`(정상), `confidence(1)`이 매우 낮음 |
| `0` | 정상(0) 확률 **최소화** | 불량이 발생하기 쉬운 조건 탐색 | 예측 `1`(불량), `confidence(0)`이 매우 낮음 |

> 사용자 질의의 단어("불량", "정상")를 `target`에 그대로 매핑하면 **반대 결과**가 나올 수 있다.
> 반드시 **사용자의 의도(방향)** 를 분류한 뒤 5장의 사전으로 변환한다.

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

| 구분 | 필드 | 설명 |
|---|---|---|
| 최적 입력값 (12개) | `incoming_material_quality_score`, `tool_wear_pct`, `planned_quantity`, `shift`, `production_line`, `process_setting_deviation_pct`, `ambient_humidity_pct`, `fixture_alignment_offset_mm`, `supplier_code`, `weld_energy_setting_pct`, `coating_target_thickness_um`, `days_since_maintenance` | 모델이 사용하는 공정 조건 |
| 결과 | `confidence(1)` | **결함(불량) 확률** |
| 결과 | `confidence(0)` | 정상 확률 |
| 결과 | `prediction(high_defect_flag)` | 예측 라벨 (`"0"` 또는 `"1"`, **문자열**) |

- 키 이름에 괄호가 있다 (`confidence(1)`). 문자열 키로 접근한다.
- 입력값 키는 **하드코딩된 목록으로 가정하지 말고**, `confidence(`, `prediction(`으로 시작하지 않는 키를 모두 공정 조건으로 취급한다. (모델이 바뀌어도 동작하도록)

### 4.4 알려진 특성 (구현 시 반드시 고려)

- 진화적 최적화라서 **같은 요청도 호출마다 결과가 조금씩 다를 수 있다.** 사용자에게 "추정값이며 호출마다 달라질 수 있음"을 안내한다.
- 응답 시간이 길 수 있다. 호출 중임을 사용자에게 알린다.
- 최적 조건에는 **현장에서 임의로 바꾸기 어려운 변수**(`shift`, `supplier_code`, `planned_quantity`, `ambient_humidity_pct`, `production_line` 등)가 포함될 수 있다. 현재 서버는 이 값들을 고정하지 않는다.
- 최적화 결과는 **모델 기반 추정**이며 실제 공정 결과를 보장하지 않는다.

### 4.5 설정 / 보안

- API 주소는 `.env`에서 읽는다. 코드와 문서에 하드코딩하지 않는다.
- `.env`가 `.gitignore`에 포함되어 있는지 확인한다. 없으면 추가한다.
- `.env.example`에는 변수명만 두고 값은 비운다.
- 인증이 필요해질 경우를 대비해 선택 환경변수(예: `OPTIMIZATION_API_TOKEN`)가 있으면 `Authorization: Bearer` 헤더를 붙이는 구조로 만든다. (현재는 인증 없이 호출됨)
- 로그에 토큰이나 사용자 질의 원문 전체를 남기지 않는다.

---

## 5. 의도 분류 및 target 매핑

### 5.1 의도(intent) 정의

LLM은 사용자 질의에서 아래 의도 중 하나를 고른다. **LLM이 `target` 숫자를 직접 출력하게 하지 않는다.** 숫자 변환은 코드의 고정 사전으로 한다.

| intent | 설명 | 동작 |
|---|---|---|
| `optimize_reduce_defect` | 불량을 줄이는 조건 / 정상(양품) 비율을 높이는 조건 탐색 | 최적화 API (`target=1`) |
| `optimize_find_defect_risk` | 불량이 발생하기 쉬운 조건 / 위험 조건 탐색 | 최적화 API (`target=0`) |
| `clarify` | 최적화 요청이지만 방향이 불분명 | API 호출 없이 되묻기 |
| `out_of_scope` | 공정 최적화와 무관한 질문 | API 호출 없이 범위 안내 |

### 5.2 intent → target 변환 (코드에서 고정)

```python
INTENT_TO_TARGET = {
    "optimize_reduce_defect": "1",     # 불량(1) 확률 최소화
    "optimize_find_defect_risk": "0",  # 정상(0) 확률 최소화 = 불량 유발 조건 탐색
}

def build_target(intent: str) -> str:
    target = INTENT_TO_TARGET.get(intent)
    if target not in ("0", "1"):
        raise ValueError(f"지원하지 않는 의도: {intent}")
    return target
```

- 사전에 없는 의도는 API를 호출하지 않는다.
- 변환 결과는 호출 직전에 `"0"` 또는 `"1"`인지 **재검증**한다.

### 5.3 질의 예시와 기대 분류

| 사용자 질의 예시 | 기대 intent | target |
|---|---|---|
| "불량을 줄이려면 공정 조건을 어떻게 해야 해?" | `optimize_reduce_defect` | 1 |
| "정상으로 나오는 최적 조건 알려줘" | `optimize_reduce_defect` | 1 |
| "양품률을 높이는 조건이 뭐야?" | `optimize_reduce_defect` | 1 |
| "불량이 가장 많이 나는 조건은?" | `optimize_find_defect_risk` | 0 |
| "위험한 공정 조건 조합 알려줘" | `optimize_find_defect_risk` | 0 |
| "최적화해줘" | `clarify` | 호출 안 함 |
| "정상으로 해줘" | `clarify` (방향 모호) | 호출 안 함 |
| "오늘 날씨 어때?" | `out_of_scope` | 호출 안 함 |

> "정상"이라는 단어가 나와도 의도가 "정상 비율을 높이고 싶다"이면 `target=1`이다. **단어가 아니라 방향**으로 판단한다.

### 5.4 LLM 구조화 출력 스키마

```json
{
  "intent": "optimize_reduce_defect",
  "reason": "사용자가 불량을 줄이는 조건을 묻고 있음"
}
```

- `intent`는 5.1의 enum 중 하나여야 한다. enum 밖의 값이 오면 `clarify`로 처리한다.
- `reason`은 디버깅용이며 사용자에게 노출하지 않는다.
- LLM 출력은 반드시 JSON 스키마(구조화 출력)로 강제하고, 파싱 실패 시 `clarify`로 처리한다.

---

## 6. 구현 요구사항

### 6.1 권장 모듈 구성 (프로젝트 상황에 맞게 조정 가능)

```
.
├── .env                      # 이미 존재 (API 주소)
├── .env.example
├── src/
│   ├── main.py               # 진입점
│   ├── chatbot.py            # 대화 흐름 오케스트레이션
│   ├── intent.py             # LLM 의도 분류 + 스키마
│   ├── optimization_client.py# 최적화 API 클라이언트
│   ├── formatter.py          # 결과 → 사용자 메시지 변환
│   └── labels.py             # 변수명 → 한글 라벨/단위 사전
├── test/
│   └── curl_test_classification.sh   # 이미 존재 (수정하지 않음)
└── tests/                    # 단위/모킹 테스트 (기존 폴더 구조가 있으면 거기에 맞출 것)
```

### 6.2 최적화 API 클라이언트

- 입력: `target: str` (`"0"`/`"1"`)
- `.env`의 주소로 GET 요청, `params={"target": target}`
- 출력: 아래 구조의 객체
  - `conditions: dict` (최적 공정 조건)
  - `defect_probability: float` (`confidence(1)`)
  - `normal_probability: float` (`confidence(0)`)
  - `predicted_label: str`
- `data`가 비었거나 필수 키가 없으면 예외 처리

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

### 6.3 대화 흐름

```
사용자 질의
   │
   ▼
LLM: intent 분류
   │
   ├─ optimize_reduce_defect ──┐
   ├─ optimize_find_defect_risk┤► build_target ─► 최적화 API ─► 결과 설명 출력
   │                           ┘
   ├─ clarify ────────────────► 방향을 되묻는 질문 (API 호출 없음)
   └─ out_of_scope ───────────► 챗봇 기능 범위 안내 (API 호출 없음)
```

### 6.4 결과 출력 형식

**공통 원칙**
- 의도에 맞는 문구를 쓴다.
  - `target=1`: "불량 확률을 낮추는 조건"
  - `target=0`: "불량이 발생하기 쉬운 조건"
- 결함 확률은 `confidence(1)`을 퍼센트로 표기한다 (소수점 1~2자리).
- 수치는 사용자가 읽기 쉽게 반올림한다 (예: 소수점 1~2자리). 단위는 `labels.py`에 정의한다.
- 마지막에 한 줄 면책 문구를 넣는다: 모델 기반 추정이며 실제 결과를 보장하지 않고, 호출마다 달라질 수 있음.

**예시 출력 (`optimize_reduce_defect`)**

```
불량 확률을 낮추는 최적 조건을 찾았어요. 이 조건에서 예상 결함 확률은 약 1.7%입니다.

| 항목 | 최적값 |
|---|---|
| 입고 자재 품질 점수 | 83.0 |
| 공구 마모율 | 12.2 % |
| 계획 수량 | 557 |
| 근무조 | 주간 (DAY) |
| ... | ... |

※ 모델 기반 추정이며 실제 공정 결과를 보장하지 않습니다. 호출할 때마다 결과가 조금씩 달라질 수 있어요.
```

**예시 출력 (`optimize_find_defect_risk`)**

```
불량이 발생하기 쉬운 조건을 찾았어요. 이 조건에서 예상 결함 확률은 약 98.3%입니다.
(표는 위와 동일한 형식)
```

### 6.5 변수명 → 한글 라벨 사전 (`labels.py`)

아래는 제안 초안이다. **실제 의미와 단위는 사용자에게 확인**하고 수정한다.

| 키 | 한글 라벨 (초안) | 단위 (초안) | `controllable` (초안) |
|---|---|---|---|
| `incoming_material_quality_score` | 입고 자재 품질 점수 | 점 | true |
| `tool_wear_pct` | 공구 마모율 | % | true |
| `planned_quantity` | 계획 수량 | 개 | false |
| `shift` | 근무조 | - | false |
| `production_line` | 생산 라인 | - | false |
| `process_setting_deviation_pct` | 공정 설정 편차 | % | true |
| `ambient_humidity_pct` | 주변 습도 | % | false |
| `fixture_alignment_offset_mm` | 지그 정렬 오프셋 | mm | true |
| `supplier_code` | 공급사 코드 | - | false |
| `weld_energy_setting_pct` | 용접 에너지 설정 | % | true |
| `coating_target_thickness_um` | 코팅 목표 두께 | μm | true |
| `days_since_maintenance` | 마지막 정비 후 경과일 | 일 | true |

- `controllable`이 `false`인 변수는 현장에서 바꾸기 어려울 수 있으므로 결과 표에서 **"참고값"** 같은 보조 표기를 단다. (어떤 변수를 `false`로 할지는 설정 파일에서 관리, 사용자 확인 필요)
- 사전에 없는 키가 응답에 오면 **키 이름 그대로** 표시하고 오류로 처리하지 않는다.
- `shift` 같은 범주 값(`DAY`, `NIGHT`)은 한글 병기 사전을 둘 수 있다 (초안: DAY=주간, NIGHT=야간, 그 외 값은 원문 그대로).

### 6.6 오류 처리

| 상황 | 처리 |
|---|---|
| 타임아웃 | "최적화 계산이 오래 걸리고 있어요. 잠시 후 다시 시도해 주세요." (재시도 1회, 설정 가능) |
| HTTP 4xx | 호출/인증 오류로 간주. 사용자에게는 일반 메시지, 로그에는 상태 코드만 기록 |
| HTTP 5xx | 서버 오류 안내, 재시도 1회 |
| JSON 파싱 실패 / `data` 비어 있음 | 오류 처리, 부분 결과 노출 금지 |
| intent가 enum 밖 / 구조화 출력 파싱 실패 | `clarify`로 처리 |
| `target`이 `"0"`/`"1"`이 아님 | 호출하지 않고 내부 오류 처리 (LLM 출력을 URL에 그대로 넣지 않는다) |
| `.env`에 API 주소가 없음 | 시작 시점에 명확한 오류 메시지로 종료 |

- 사용자에게 스택트레이스나 내부 URL을 노출하지 않는다.

### 6.7 로깅

- `intent`, `target`, 소요 시간, 상태 코드를 기록한다.
- 원문 질의 전체와 토큰은 기록하지 않는다.

---

## 7. 비기능 요구사항

- 응답 대기 중 사용자에게 진행 상태를 보여 준다 ("최적화 중이에요…" 등).
- API 주소, 타임아웃, 재시도 횟수는 설정(환경변수 또는 설정 파일)으로 분리한다.
- 설정과 비즈니스 로직(의도 → target 변환)은 **LLM 호출과 분리**해 단위 테스트가 가능하게 한다.

---

## 8. 테스트

### 8.1 단위 테스트

- `build_target`: 각 intent → 기대 target, 미정의 intent → 예외
- `parse_optimization_response`: 정상 응답, 빈 `data`, 필수 키 누락, 알 수 없는 입력 키 포함
- 포맷터: `target=1`/`target=0` 각각 문구, 확률 퍼센트 표기, 라벨 사전에 없는 키 처리
- intent 파싱 실패/enum 밖 값 → `clarify`

### 8.2 모킹 통합 테스트

- 최적화 API를 **모킹**해서 전체 흐름 확인 (질의 → intent → target → 응답 → 출력)
- 요청에 `?target=1`, `?target=0`이 올바르게 붙는지 확인
- 타임아웃, 4xx, 5xx, 빈 응답에서 사용자 메시지가 안전한지 확인

### 8.3 수동 검증 (실제 엔드포인트, 개발 환경에서만)

1. `test/curl_test_classification.sh`로 API가 응답하는지 먼저 확인한다.
2. `target=1`과 `target=0`으로 각각 호출해 결과가 **서로 다른지** 확인한다. (서버 기본값이 `1`이라 같은 값만 호출하면 매크로 반영 여부를 알 수 없다)
3. 같은 `target`을 두세 번 호출해 결과 변동 폭을 확인한다.
4. 응답 시간을 측정해 타임아웃 기본값이 적절한지 확인한다.
5. 5.3의 질의 예시를 실제 챗봇에 입력해 분류 결과가 기대와 일치하는지 확인한다.

---

## 9. 완료 기준 (Acceptance Criteria)

- [ ] "불량을 줄이는 조건" 류의 질의가 `target=1`로 호출된다.
- [ ] "불량이 잘 나는 조건" 류의 질의가 `target=0`으로 호출된다.
- [ ] 방향이 모호한 질의는 API 호출 없이 되묻는다.
- [ ] 무관한 질문은 API 호출 없이 범위를 안내한다.
- [ ] 결과에 최적 조건 표와 예상 결함 확률이 출력된다.
- [ ] 출력 문구가 의도(`target`)에 맞다 ("낮추는 조건" / "발생하기 쉬운 조건").
- [ ] 면책 문구(모델 기반 추정, 결과 변동 가능)가 출력된다.
- [ ] 타임아웃·4xx·5xx·빈 응답에서 사용자에게 안전한 메시지가 나온다.
- [ ] API 주소와 토큰이 코드에 하드코딩되어 있지 않고, `.env`가 `.gitignore`에 포함되어 있다.
- [ ] 단위 테스트와 모킹 통합 테스트가 통과한다.

---

## 10. 향후 확장 후보 (이번 범위 아님)

- 임의 공정 조건에 대한 결함률 예측 (별도 예측 엔드포인트 연동)
- 서버 측에서 조절 불가 변수를 고정하는 방식
- 이전 결과를 기억해 "야간조만 아니면?" 같은 후속 질문 처리
- 웹 UI

---

## 11. 열린 질문 (구현 전에 확인할 것)

Cursor는 프로젝트 폴더에서 확인 가능한 항목은 직접 확인하고, 확인이 안 되는 항목은 구현 전에 사용자에게 질문한다.

1. `.env`에서 API 주소의 변수명은? 다른 설정 변수(LLM 키 등)가 이미 있는가?
2. `test/curl_test_classification.sh`는 최적화 API를 호출하는가? 필요한 헤더나 인증 방식이 있는가?
3. 사용할 **언어/프레임워크**와 **LLM 제공자**는? (구조화 출력/JSON 스키마를 지원해야 함)
4. **UI 형태**는? (기본 가정: 1차는 터미널 CLI 대화. 웹 UI가 필요하면 알려줄 것)
5. 6.5의 한글 라벨, 단위, `controllable` 값이 실제 공정 의미와 맞는가?
6. 조절 불가 변수를 결과에서 숨길지, "참고값"으로 표시할지?
7. 최적화 API의 정상 응답 시간(수 초? 수십 초?)은? 타임아웃과 로딩 UI에 영향.
8. 챗봇 응답 언어는 한국어로 고정하는가?
