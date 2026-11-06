# 모델 로직

## 입력 변수 (공통 12개)

| 변수명 | 타입 | 설명 | 범위 |
|--------|------|------|------|
| `production_line` | string | 생산 라인 | LINE-BPR-01, LINE-BPR-02 |
| `shift` | string | 근무 교대 | DAY, NIGHT |
| `supplier_code` | string | 공급업체 코드 | SIM-SUP-A, SIM-SUP-B, SIM-SUP-C |
| `planned_quantity` | int | 계획 생산량 | ≥ 0 |
| `ambient_humidity_pct` | float | 주변 습도 (%) | 0 – 100 |
| `incoming_material_quality_score` | float | 입고 자재 품질 점수 | 0 – 100 |
| `coating_target_thickness_um` | float | 코팅 목표 두께 (μm) | ≥ 0 |
| `weld_energy_setting_pct` | float | 용접 에너지 설정값 (%) | 0 – 150 |
| `fixture_alignment_offset_mm` | float | 지그 정렬 편차 (mm) | ≥ 0 |
| `process_setting_deviation_pct` | float | 공정 설정 편차 (%) | 음수 허용 |
| `tool_wear_pct` | float | 공구 마모율 (%) | 0 – 100 |
| `days_since_maintenance` | int | 마지막 정비 후 경과일 | ≥ 0 |

---

## 회귀 모델 (GBT Regression)

### 목적
공정 변수 12개로부터 **결함률(%)** 을 예측한다.

### 출력
| 필드 | 타입 | 설명 |
|------|------|------|
| `prediction(defect_rate_pct)` | float | 예측 결함률 (%) |

### 등급 판정 (Panopticon Python Transform 내)
```python
if defect_rate_pct < 3.0:
    level = "양호 (Good)"
elif defect_rate_pct < 7.0:
    level = "주의 (Warning)"
else:
    level = "불량 (Poor)"
```

### AI Studio 배포 프로세스 (`deploy.rmp`)
```
외부 입력(12개 변수) → 타입 변환 → GBT 회귀 모델 적용
→ prediction(defect_rate_pct) 반환
```

### API 호출 예시
```bash
curl -X POST "https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_rate_pred/deploy" \
  -H "Content-Type: application/json" \
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

## 분류 모델 (GBT Classification)

### 목적
공정 변수 12개로부터 **고결함 여부(0/1)** 를 예측한다.

### 출력
| 필드 | 타입 | 설명 |
|------|------|------|
| `prediction(high_defect_flag)` | string | "0" = 정상, "1" = 고결함 |
| `confidence(0)` | float | 정상일 확률 |
| `confidence(1)` | float | 고결함일 확률 |

### 레이블 정의
| 값 | 의미 |
|----|-----|
| 0 | normal (정상 조건) |
| 1 | abnormal (고결함 조건) |

---

## 최적화 프로세스 (Prescriptive Analytics)

### 목적
분류 모델 + Prescriptive Analytics(Evolutionary)로 목표 조건에 맞는 **최적 공정조건 1세트** 를 탐색한다.

### 매크로 `target`

| 값 | 의미 | 활용 |
|----|-----|------|
| `"1"` | 불량(1) 확률 최소화 → 개선 조건 탐색 | defect-advisor `optimize_reduce_defect`, `predict_and_optimize` |
| `"0"` | 정상(0) 확률 최소화 → 위험 조건 탐색 | defect-advisor `optimize_find_defect_risk`, `predict_and_find_risk` |

### AI Studio 배포 프로세스 (`deploy-optimization.rmp`)
```
매크로 target 주입
→ 학습 데이터 로드 (ICX_train_classification_final)
→ GBT 분류 모델 적용
→ Prescriptive Analytics (Evolutionary) — target 방향으로 탐색
→ 최적 공정조건 1행 반환
```

### API 호출 예시
```bash
# 개선 조건 탐색 (target=1)
curl "https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization?target=1"

# 위험 조건 탐색 (target=0)
curl "https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization?target=0"
```

### 응답 예시
```json
{
  "data": [{
    "production_line": "LINE-BPR-01",
    "shift": "DAY",
    "supplier_code": "SIM-SUP-A",
    "planned_quantity": 480,
    "ambient_humidity_pct": 35.2,
    "incoming_material_quality_score": 95.1,
    "coating_target_thickness_um": 72.0,
    "weld_energy_setting_pct": 88.0,
    "fixture_alignment_offset_mm": 0.05,
    "process_setting_deviation_pct": 0.3,
    "tool_wear_pct": 12.0,
    "days_since_maintenance": 3,
    "confidence(1)": 0.0183,
    "confidence(0)": 0.9817,
    "prediction(high_defect_flag)": "0"
  }]
}
```

---

## 하위 프로젝트 연동 로직

### defect-predictor

```
한국어 질의
  → LLM(QueryExtractor): 슬롯 12개 추출
  → SlotFillingSession.merge(): 누락 슬롯 추적
  → 검증(DefectRateInput)
  → DefectRateMLClient.predict(): POST /deploy
  → LLM 해설 생성
```

**상태**: `ok` / `need_more_info` / `invalid_input` / `endpoint_error` / `llm_error`  
**재시도**: 타임아웃·5xx → 최대 2회, 지수 백오프 (0.5s→1s→2s)

### defect-advisor intent 분기

| intent | 회귀 API | 최적화 API | target |
|--------|---------|-----------|--------|
| `predict` | ✓ | — | — |
| `predict_and_optimize` | ✓ | ✓ | "1" |
| `predict_and_find_risk` | ✓ | ✓ | "0" |
| `optimize_reduce_defect` | — | ✓ | "1" |
| `optimize_find_defect_risk` | — | ✓ | "0" |
| `clarify` | — | — | — |

**설계 원칙**: LLM은 intent 문자열만 판단. `target` 값 변환은 `INTENT_TO_TARGET` 사전이 담당(LLM 환각 방지).  
**부분 성공**: 최적화 실패 시에도 `status="ok"`, `optimization=null` + `errors` 필드로 판단.
