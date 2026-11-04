# 외부 엔드포인트 명세

defect-advisor가 송수신하는 외부 HTTP 엔드포인트 두 개를 기술한다.  
LLM 게이트웨이(SDC)는 별도 서비스이며 이 문서에서는 다루지 않는다.

---

## 1. ML 예측 API

### 개요

| 항목 | 값 |
|---|---|
| 역할 | 공정 조건 12개를 받아 결함률(%)을 예측한다 |
| 메서드 | `POST` |
| URL | `AI_HUB_ENDPOINT_URL` (.env) |
| 인증 | `Authorization: Bearer <AI_HUB_API_KEY>` (키가 없으면 헤더 생략) |
| 콘텐츠 타입 | `Content-Type: application/json` / `Accept: application/json` |
| 구현 파일 | `aihub/ml.py` — `DefectRateMLClient` |

### 요청

#### 헤더

```http
POST {AI_HUB_ENDPOINT_URL}
Content-Type: application/json
Accept: application/json
Authorization: Bearer <api_key>
```

#### 본문 스키마

```json
{
  "data": [
    { /* DefectRateInput 레코드, 1개 이상 */ }
  ]
}
```

`data` 배열의 각 요소는 아래 12개 필드를 모두 포함해야 한다.

| 필드 | 타입 | 허용값 / 범위 | 설명 |
|---|---|---|---|
| `production_line` | string | `LINE-BPR-01`, `LINE-BPR-02` | 생산 라인 코드 |
| `shift` | string | `DAY`, `NIGHT` | 교대조 |
| `supplier_code` | string | `SIM-SUP-A`, `SIM-SUP-B`, `SIM-SUP-C` | 공급사 코드 |
| `planned_quantity` | integer | ≥ 0 | 계획 생산 수량(개) |
| `ambient_humidity_pct` | number | 0 – 100 | 작업장 습도(%) |
| `incoming_material_quality_score` | number | 0 – 100 | 입고 자재 품질점수 |
| `coating_target_thickness_um` | number | ≥ 0 | 코팅 목표 두께(μm) |
| `weld_energy_setting_pct` | number | 0 – 150 | 용접 에너지 설정(%) |
| `fixture_alignment_offset_mm` | number | ≥ 0 | 지그 정렬 오프셋(mm) |
| `process_setting_deviation_pct` | number | 제한 없음(음수 허용) | 공정 설정 편차(%) |
| `tool_wear_pct` | number | 0 – 100 | 공구 마모도(%) |
| `days_since_maintenance` | integer | ≥ 0 | 마지막 정비 후 경과 일수 |

문자열 필드는 전송 전에 공백 제거 및 대문자 정규화가 적용된다(`schema.py:DefectRateInput._normalize_text`).

#### 요청 예시

```json
{
  "data": [
    {
      "production_line": "LINE-BPR-01",
      "shift": "DAY",
      "supplier_code": "SIM-SUP-B",
      "planned_quantity": 500,
      "ambient_humidity_pct": 52.0,
      "incoming_material_quality_score": 80.0,
      "coating_target_thickness_um": 80.0,
      "weld_energy_setting_pct": 100.0,
      "fixture_alignment_offset_mm": 0.10,
      "process_setting_deviation_pct": 0.0,
      "tool_wear_pct": 45.0,
      "days_since_maintenance": 10
    }
  ]
}
```

### 응답

#### 정상 응답 (HTTP 200)

```json
{
  "data": [
    {
      "production_line": "LINE-BPR-01",
      "shift": "DAY",
      "supplier_code": "SIM-SUP-B",
      "planned_quantity": 500,
      "ambient_humidity_pct": 52.0,
      "incoming_material_quality_score": 80.0,
      "coating_target_thickness_um": 80.0,
      "weld_energy_setting_pct": 100.0,
      "fixture_alignment_offset_mm": 0.10,
      "process_setting_deviation_pct": 0.0,
      "tool_wear_pct": 45.0,
      "days_since_maintenance": 10,
      "prediction(defect_rate_pct)": 1.65
    }
  ]
}
```

응답의 최상위 구조는 `{"data": [...]}` 또는 배열 자체 두 형식을 모두 허용한다.  
예측값 키 이름은 `ai_hub_prediction_column` 설정으로 변경할 수 있다(기본값: `prediction(defect_rate_pct)`).

#### 응답 필드

| 필드 | 설명 |
|---|---|
| `prediction(defect_rate_pct)` | 예측 결함률. 값 자체가 % 단위(1.65 = 1.65%). 추가 배율 변환 불필요 |
| 입력 12개 필드 (에코) | 요청 그대로 반환. 존재 여부만 검사하며 값 동일성은 보장하지 않음 |

### 제약 및 동작 규칙

- **레코드 순서 보장**: 응답의 `data` 배열은 요청과 동일한 순서라고 가정한다. 별도 식별자로 재정렬하지 않는다.
- **에코 검증**: 전송한 12개 필드가 응답에 모두 존재해야 한다. `AI_HUB_STRICT_ECHO=true`(기본값)이면 누락 시 오류 처리, `false`이면 경고만 남기고 진행한다.
- **재시도 정책**: 타임아웃·5xx에 대해 최대 `AI_HUB_MAX_RETRIES`(기본값 2)회 재시도. 지수 백오프(0.5s → 1s → 2s). 4xx는 즉시 실패.
- **타임아웃**: `AI_HUB_TIMEOUT_SECONDS`(기본값 30초).
- **SSL 검증**: `AI_HUB_VERIFY_SSL=false`(.env)로 비활성화 가능. 사내 인증서 환경용.
- **모의 모드**: `MOCK_ML=true`이면 API를 호출하지 않고 순서 기반 더미값(1.65%, 2.65%, ...)을 반환한다.

### curl 예시

```bash
curl -X POST "$AI_HUB_ENDPOINT_URL" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -H "Authorization: Bearer $AI_HUB_API_KEY" \
     -d '{
       "data": [{
         "production_line": "LINE-BPR-01",
         "shift": "DAY",
         "supplier_code": "SIM-SUP-B",
         "planned_quantity": 500,
         "ambient_humidity_pct": 52.0,
         "incoming_material_quality_score": 80.0,
         "coating_target_thickness_um": 80.0,
         "weld_energy_setting_pct": 100.0,
         "fixture_alignment_offset_mm": 0.10,
         "process_setting_deviation_pct": 0.0,
         "tool_wear_pct": 45.0,
         "days_since_maintenance": 10
       }]
     }'
```

---

## 2. 최적화 API

### 개요

| 항목 | 값 |
|---|---|
| 역할 | `target` 방향에 따라 결함 확률을 최소화하는 최적 공정 조건 1세트를 반환한다 |
| 메서드 | `GET` |
| URL | `OPTIMIZATION_API_URL` (.env) |
| 인증 | `Authorization: Bearer <OPTIMIZATION_API_TOKEN>` (토큰이 없으면 헤더 생략) |
| 구현 파일 | `aihub/optimization.py` — `OptimizationClient` |

입력 조건을 전송하는 ML 예측 API와 달리, 최적화 API는 방향(`target`)만 지정하면 서버가 최적 조건을 계산해 반환한다.

### 요청

#### 헤더 및 파라미터

```http
GET {OPTIMIZATION_API_URL}?target={0|1}
Accept: application/json
Authorization: Bearer <OPTIMIZATION_API_TOKEN>
```

#### 쿼리 파라미터

| 파라미터 | 타입 | 허용값 | 설명 |
|---|---|---|---|
| `target` | string | `"0"`, `"1"` | `"1"`: 불량 확률 최소화(개선 조건 탐색) / `"0"`: 정상 확률 최소화(불량 위험 조건 탐색) |

`target` 값은 LLM이 직접 선택하지 않는다. `optimization.py:INTENT_TO_TARGET`과 `build_target()`이 챗봇 의도(intent)를 변환한다.

| intent | target | 의미 |
|---|---|---|
| `optimize_reduce_defect` | `"1"` | 불량 감소를 위한 최적 조건 |
| `predict_and_optimize` | `"1"` | 예측 후 불량 감소 조건 추가 탐색 |
| `optimize_find_defect_risk` | `"0"` | 불량 유발 위험 조건 탐색 |
| `predict_and_find_risk` | `"0"` | 예측 후 불량 위험 조건 추가 탐색 |

### 응답

#### 정상 응답 (HTTP 200)

`target="0"` 예시 (`test/results/api/out_0.json`):

```json
{
  "data": [
    {
      "incoming_material_quality_score": 78.678,
      "tool_wear_pct": 68.937,
      "planned_quantity": 532.0,
      "shift": "NIGHT",
      "production_line": "LINE-BPR-01",
      "process_setting_deviation_pct": 11.111,
      "ambient_humidity_pct": 75.371,
      "fixture_alignment_offset_mm": 0.262,
      "supplier_code": "SIM-SUP-C",
      "weld_energy_setting_pct": 91.626,
      "coating_target_thickness_um": 71.551,
      "days_since_maintenance": 47.0,
      "confidence(1)": 0.9895,
      "confidence(0)": 0.0105,
      "prediction(high_defect_flag)": "1"
    }
  ]
}
```

`target="1"` 예시 (`test/results/api/out_1.json`):

```json
{
  "data": [
    {
      "incoming_material_quality_score": 96.199,
      "tool_wear_pct": 11.981,
      "planned_quantity": 482.0,
      "shift": "DAY",
      "production_line": "LINE-BPR-02",
      "process_setting_deviation_pct": 2.059,
      "ambient_humidity_pct": 45.434,
      "fixture_alignment_offset_mm": 0.875,
      "supplier_code": "SIM-SUP-A",
      "weld_energy_setting_pct": 111.446,
      "coating_target_thickness_um": 97.660,
      "days_since_maintenance": 57.0,
      "confidence(1)": 0.0183,
      "confidence(0)": 0.9817,
      "prediction(high_defect_flag)": "0"
    }
  ]
}
```

#### 응답 필드

| 필드 | 타입 | 설명 |
|---|---|---|
| `confidence(1)` | float | 해당 조건이 불량(`high_defect_flag=1`)으로 예측될 확률 |
| `confidence(0)` | float | 해당 조건이 정상(`high_defect_flag=0`)으로 예측될 확률 |
| `prediction(high_defect_flag)` | string | 모델의 최종 예측 라벨 (`"0"` 또는 `"1"`) |
| 입력 12개 필드 | mixed | 최적화된 공정 조건 값. `float`으로 반환될 수 있음(`days_since_maintenance` 등) |

파싱 결과는 `parse_optimization_response()`가 아래 형태로 변환한다:

```python
{
    "conditions": { /* confidence·prediction 제외 12개 필드 */ },
    "defect_probability": 0.9895,    # confidence(1)
    "normal_probability":  0.0105,   # confidence(0)
    "predicted_label":    "1",       # prediction(high_defect_flag)
    "latency_ms": 1240,
    "target": "0"
}
```

### 제약 및 동작 규칙

- **단방향 탐색**: 서버가 최적 조건을 결정한다. 클라이언트는 `target`만 지정하며 조건 값을 전송하지 않는다.
- **`target` 매핑 주의**: `INTENT_TO_TARGET` 사전이 틀리면 탐색 방향이 반대로 뒤집힌다. 자동 테스트가 없으므로 운영 API로 교차 검증이 필요하다.
- **재시도 정책**: 타임아웃·5xx에 대해 최대 `OPTIMIZATION_MAX_RETRIES`(기본값 1)회 재시도. 4xx는 즉시 실패.
- **타임아웃**: `OPTIMIZATION_TIMEOUT_SECONDS`(기본값 180초). curl 테스트 기준 응답이 느릴 수 있어 넉넉하게 설정되어 있다.
- **선택적 기동**: `OPTIMIZATION_API_URL`이 없어도 서버는 시작된다. 실제로 최적화 의도를 요청할 때 `OptimizationEndpointError`가 발생한다.
- **부분 성공**: `predict_and_optimize` / `predict_and_find_risk` 경로에서 최적화 API가 실패해도 파이프라인은 `status="ok"`를 반환한다. `optimization=null` + `errors` 필드로 실패를 확인해야 한다.

### curl 예시

```bash
# target=1: 불량 확률을 낮추는 최적 조건
curl -G "$OPTIMIZATION_API_URL" \
     --data-urlencode "target=1" \
     -H "Accept: application/json" \
     -H "Authorization: Bearer $OPTIMIZATION_API_TOKEN"

# target=0: 불량을 유발하는 위험 조건
curl -G "$OPTIMIZATION_API_URL" \
     --data-urlencode "target=0" \
     -H "Accept: application/json" \
     -H "Authorization: Bearer $OPTIMIZATION_API_TOKEN"
```

---

## 관련 설정 요약 (.env)

| 환경 변수 | 대상 API | 기본값 | 필수 |
|---|---|---|---|
| `AI_HUB_ENDPOINT_URL` | ML 예측 | — | ✓ (`MOCK_ML=true` 시 생략 가능) |
| `AI_HUB_API_KEY` (또는 `api_key`) | ML 예측 | — | 인증 필요 시 |
| `AI_HUB_VERIFY_SSL` | ML 예측 | `true` | — |
| `AI_HUB_TIMEOUT_SECONDS` | ML 예측 | `30.0` | — |
| `AI_HUB_MAX_RETRIES` | ML 예측 | `2` | — |
| `AI_HUB_STRICT_ECHO` | ML 예측 | `true` | — |
| `OPTIMIZATION_API_URL` | 최적화 | — | 최적화 기능 사용 시 |
| `OPTIMIZATION_API_TOKEN` | 최적화 | — | 인증 필요 시 |
| `OPTIMIZATION_TIMEOUT_SECONDS` | 최적화 | `180.0` | — |
| `OPTIMIZATION_MAX_RETRIES` | 최적화 | `1` | — |
| `MOCK_ML` | ML 예측 | `false` | — |

---

## 변경 이력

- **2026-11-03**: 초기 작성 — ML 예측 API와 최적화 API의 URL, 파라미터, 송수신 예시, 스키마, 제약 및 설정 요약을 기술했다.
