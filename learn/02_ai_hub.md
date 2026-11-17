# AI Hub

Altair AI Hub는 AI Studio에서 학습한 모델(프로세스)을 **REST API 엔드포인트**로 외부에 공개하는 MLOps 플랫폼입니다.  
AI Studio와 연동되어 있어, Studio에서 만든 배포 프로세스를 그대로 AI Hub에 올릴 수 있습니다.

---

## 1. 핵심 개념

### 서비스(Service)

배포 단위입니다. AI Studio에서 만든 `.rmp` 프로세스(배포 프로세스)를 스냅샷으로 패키징해 AI Hub에 등록합니다.  
등록된 서비스는 고유한 REST API URL을 갖습니다.

### 엔드포인트(Endpoint)

서비스가 외부 클라이언트에 노출하는 HTTP URL입니다.

```
https://<host>/webapi/<group>/api/v1/services/<service-name>/<deploy-name>
```

예시 (이 프로젝트 기준):

```
POST https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_rate_pred/deploy
GET  https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization
```

### 스냅샷(Snapshot)

배포 시점의 프로세스와 모델을 고정한 버전입니다. 이후 Studio에서 프로세스를 수정해도 배포된 스냅샷에는 영향을 주지 않습니다.

---

## 2. 배포 절차

```
1. AI Studio에서 배포 프로세스(.rmp) 작성
        │
        ▼
2. AI Studio Repository에 프로세스 저장
        │
        ▼
3. AI Hub 접속 → Services → 새 서비스 생성
        │
        ▼
4. 서비스에 프로세스 연결 → 스냅샷 생성 → 배포(Deploy)
        │
        ▼
5. 엔드포인트 URL 확인 → 외부 클라이언트에 공유
```

---

## 3. 이 프로젝트의 엔드포인트

### hd-modeling (공정 결함 예측)

> **참고 프로젝트**: `hd-modeling/`

| 용도 | 메서드 | URL |
|------|--------|-----|
| 결함률 예측 (GBT 회귀) | `POST` | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_rate_pred/deploy` |
| 최적 공정조건 추천 (GBT 분류+최적화) | `GET` | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization` |

**배포 모델**:

| 서비스 | 모델 파일 |
|--------|----------|
| `defect_rate_pred` | `strore-regression-gbt-v0.2.rmmodel` |
| `defect_flag_classification` | `strore-classification-gbt-v0.3.rmmodel` |

---

### nice-modeling (신용평가)

> **참고 프로젝트**: `nice-modeling/`

| 버전 | URL | 상태 |
|------|-----|------|
| **v2 현행** | `https://mlops.nice.plda-cloud.com/webapi/DEFAULT/api/v1/services/nice-scoring/deploy_scoring_process_v02` | ✅ 운영 중 |
| v1 구 | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/nice_score/deploy_scoring_process` | ⚠️ ExecutionError |

**배포 모델**: `261109_ext_lightgbm.rmtabmod` (LightGBM Extension 1.0.4)

---

## 4. API 호출 방법

### POST — 결함률 예측

요청:

```http
POST https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_rate_pred/deploy
Content-Type: application/json

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

응답:

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
      "fixture_alignment_offset_mm": 0.1,
      "process_setting_deviation_pct": 0.0,
      "tool_wear_pct": 45.0,
      "days_since_maintenance": 10,
      "prediction(defect_rate_pct)": 1.65
    }
  ]
}
```

**포인트**: 입력 필드 전체가 에코되고, `prediction(컬럼명)` 형태로 예측값이 추가됩니다.

---

### GET — 최적 공정조건 추천

요청:

```http
GET https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization?target=1
```

`target` 값의 의미:

| `target` | 의미 |
|----------|------|
| `1` | 불량을 줄이는 최적 조건 탐색 (고위험 → 최소화) |
| `0` | 불량이 잘 발생하는 위험 조건 탐색 |

응답:

```json
{
  "data": [
    {
      "production_line": "LINE-BPR-01",
      "shift": "DAY",
      "supplier_code": "SIM-SUP-A",
      "planned_quantity": 510,
      "ambient_humidity_pct": 45.2,
      "incoming_material_quality_score": 92.1,
      "coating_target_thickness_um": 85.0,
      "weld_energy_setting_pct": 95.0,
      "fixture_alignment_offset_mm": 0.05,
      "process_setting_deviation_pct": 0.5,
      "tool_wear_pct": 20.0,
      "days_since_maintenance": 5,
      "confidence(1)": 0.02,
      "confidence(0)": 0.98,
      "prediction(high_defect_flag)": "0"
    }
  ]
}
```

---

### Python에서 호출하는 방법

> **참고 프로젝트**: `defect-predictor/aihub/ml.py`, `defect-advisor/aihub/optimization.py`

```python
import httpx

# 결함률 예측 (POST)
url = "https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_rate_pred/deploy"

payload = {
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
}

response = httpx.post(url, json=payload, timeout=30)
result = response.json()
defect_rate = result["data"][0]["prediction(defect_rate_pct)"]
print(f"예측 결함률: {defect_rate}%")
```

```python
# 최적 공정조건 추천 (GET)
opt_url = "https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization"

response = httpx.get(opt_url, params={"target": "1"}, timeout=60)
result = response.json()
optimal_conditions = result["data"][0]
print(optimal_conditions)
```

---

## 5. 입력 스키마 (공정 결함 모델)

> **참고 프로젝트**: `defect-predictor/aihub/schema.py`, `defect-dashboard/CLAUDE.md`

| 필드명 | 타입 | 범위 / 허용값 |
|--------|------|--------------|
| `production_line` | 범주형 | `LINE-BPR-01`, `LINE-BPR-02` |
| `shift` | 범주형 | `DAY`, `NIGHT` |
| `supplier_code` | 범주형 | `SIM-SUP-A`, `SIM-SUP-B`, `SIM-SUP-C` |
| `planned_quantity` | 정수 | 440 ~ 561 |
| `ambient_humidity_pct` | 실수 | 28 ~ 86 |
| `incoming_material_quality_score` | 실수 | 70.8 ~ 99 |
| `coating_target_thickness_um` | 실수 | 62 ~ 121 |
| `weld_energy_setting_pct` | 실수 | 76 ~ 118 |
| `fixture_alignment_offset_mm` | 실수 | 0.02 ~ 1.6 |
| `process_setting_deviation_pct` | 실수 | 0.05 ~ 16 |
| `tool_wear_pct` | 실수 | 2 ~ 83.9 |
| `days_since_maintenance` | 정수 | 1 ~ 60 |

---

## 6. 주요 팁

- **`data` 배열에 여러 행을 담으면 한 번의 요청으로 배치 예측이 가능합니다.** AI Hub는 레코드 단위로 모델을 적용해 각각의 결과를 반환합니다.
- **응답은 입력을 에코합니다.** 예측값 외에도 입력 필드가 그대로 포함됩니다. 클라이언트 측에서 `prediction(...)` 키만 추출해 사용하세요.
- **최적화 API는 응답 시간이 길 수 있습니다.** Prescriptive Analytics(Evolutionary) 탐색 과정 때문입니다. 타임아웃을 넉넉히 잡으세요 (60초 이상 권장).
- **인증**: 현재 엔드포인트는 인증 헤더 없이 호출합니다. 운영 환경에서는 API Key나 토큰 인증이 필요할 수 있습니다.
