# 입력 필드 정의 (Input Schema)

결함률 예측 엔드포인트에 전달되는 입력 필드 12개에 대한 설명입니다.
**유효값 제약**은 확정된 사양이고, **관측 범위**는 골든 셋(`data/golden_set_v2.json`, v2.0)과 실제 데이터에서 관측된 값으로 참고용입니다. (v1 골든 셋은 `data/v1/golden_set.json`에 보관되어 있습니다.) 필드 설명은 필드명과 데이터에서 정리한 내용입니다.

## 필드 목록

| # | 필드 | 타입 | 단위 | 설명 | 유효값 제약 | 관측 범위 | 비고 |
|---|---|---|---|---|---|---|---|
| 1 | `production_line` | string | - | 생산 라인 코드 | `LINE-BPR-01`, `LINE-BPR-02` | - | 실제 라인은 2종뿐 |
| 2 | `shift` | string | - | 근무조(주간/야간) | `DAY`, `NIGHT` | - | 질의의 "주간조", "밤 근무", "day shift" 등은 코드로 변환 |
| 3 | `supplier_code` | string | - | 입고 자재 공급사 코드 | `SIM-SUP-A`, `SIM-SUP-B`, `SIM-SUP-C` | - | A 비중이 가장 높음 |
| 4 | `planned_quantity` | int | 개 | lot 계획 생산 수량 | - | 약 440 ~ 561 | |
| 5 | `ambient_humidity_pct` | float | % | 작업장 상대습도 | - | 약 28 ~ 86 | |
| 6 | `incoming_material_quality_score` | float | 점 | 수입검사 원자재 품질 점수 | - | 약 62 ~ 99 | 값이 높을수록 양호 |
| 7 | `coating_target_thickness_um` | float | µm | 코팅 목표 두께 | - | 약 62 ~ 120 | 질의가 mm이면 ×1000 환산 (예: 0.08mm → 80.0) |
| 8 | `weld_energy_setting_pct` | float | % | 용접 에너지 설정값 | - | 약 76 ~ 118 | 기준 100% 대비 |
| 9 | `fixture_alignment_offset_mm` | float | mm | 지그(fixture) 정렬 오차 | **0 이상** (0 유효, 음수 불가) | 약 0.02 ~ 1.6 | 단위 변환 없이 mm 그대로 유지 |
| 10 | `process_setting_deviation_pct` | float | % | 공정 설정값의 표준 대비 이탈 정도 | - | 약 0 ~ 16 | |
| 11 | `tool_wear_pct` | float | % | 공구 마모율 | **0 ~ 100** (0, 100 유효) | 약 2 ~ 84 | 범위 밖 값은 오류 케이스 (I01: 140, I02: -5) |
| 12 | `days_since_maintenance` | int | 일 | 마지막 설비 정비 후 경과일 | - | 약 1 ~ 60 | |

### 유효값 제약 요약

- `production_line`: `LINE-BPR-01`, `LINE-BPR-02` 외의 값은 존재하지 않음
- `shift`: `DAY`, `NIGHT`
- `supplier_code`: `SIM-SUP-A`, `SIM-SUP-B`, `SIM-SUP-C`
- `fixture_alignment_offset_mm`: 0 이상 (음수 입력은 유효하지 않음)
- `tool_wear_pct`: 0~100 (초과·미만 값은 오류 케이스)

### 현재 코드의 추가 검사 (사양 아님)

<!-- [추가] 2026-10-22: 사양에는 없지만 schema.py DefectRateInput이 차단하는 범위를 명시 -->

위 표에서 유효값 제약이 `-`인 필드도 현재 코드(`aihub/schema.py`의 `DefectRateInput`)는 아래 범위를 검사하고, 벗어나면 `invalid_input`으로 차단합니다. 확정된 사양이 아니며, 유지 여부는 [`architecture.md`](./architecture.md)의 미결 사항에서 관리합니다.

- `planned_quantity`, `days_since_maintenance`: 0 이상 정수 (추출 단계에서 정수로 반올림)
- `ambient_humidity_pct`, `incoming_material_quality_score`: 0~100
- `coating_target_thickness_um`: 0 이상
- `weld_energy_setting_pct`: 0~150
- `process_setting_deviation_pct`: 범위 검사 없음 (음수 허용)

### 레코드 예시 (C01)

```json
{
  "production_line": "LINE-BPR-01",
  "shift": "DAY",
  "supplier_code": "SIM-SUP-B",
  "planned_quantity": 533,
  "ambient_humidity_pct": 54.49,
  "incoming_material_quality_score": 83.95,
  "coating_target_thickness_um": 79.22,
  "weld_energy_setting_pct": 92.67,
  "fixture_alignment_offset_mm": 0.112,
  "process_setting_deviation_pct": 13.06,
  "tool_wear_pct": 14.41,
  "days_since_maintenance": 30
}
```

## 공통 규칙

- **값이 없는 경우**: 질의에서 값을 알 수 없으면 해당 필드를 `null`로 두고 `missing_fields`에 필드명을 넣으며, `status`는 `need_more_info`가 됩니다. 누락된 값을 `0` 등으로 채우지 않습니다 (P02).
- **`missing_fields` 구성** <!-- [추가] 2026-10-22: N05(범위 밖 질의) 기대값과 규칙을 일치시키기 위해 명시 -->
  - 기본: 모든 레코드의 `null` 필드 합집합(중복 없음)
  - `invalid_input`: `[]`
  - 예측 요청이 아닌 질의(`records = []`): 추출된 입력이 하나도 없으므로 **12개 필드 전체** (N05)
- **예측 의도 판단과 `records`** <!-- [추가] 2026-10-22: 골든 셋에서 암묵적으로 쓰이던 판단 기준을 명시 -->
  - 예측 의도가 있으면 레코드 1개 이상을 만들고, 값이 전혀 없으면 12개 필드가 모두 `null`인 레코드 1개를 둡니다 (N01~N03).
  - "결함률 예측" 같은 문구 없이 공정 조건만 나열해도 예측 의도로 봅니다 (A01~A05, A07, P08).
  - 예측에 필요한 입력을 묻는 질문도 예측 의도로 보고 전 필드 `null` 레코드를 둡니다 (N04).
  - 공정·예측과 무관한 질의만 `records = []`입니다 (N05).
- **모호한 값**: 값이 있어도 하나로 확정할 수 없으면 `null`로 두고 `ambiguous_fields`에도 필드명을 넣습니다. `status`는 `need_more_info`이며, `ambiguous_fields`는 `missing_fields`의 부분집합입니다 (A01~A07).

  | 유형 | 예시 |
  |---|---|
  | 정성·상대 표현 | "평소보다 높다", "꽤 닳았다", "얼마 전에 정비" |
  | 범위 표현 | "습도 50에서 60% 사이", "460~470개" |
  | 단위 없는 값 | 코팅 두께 "0.08" (mm인지 µm인지 불명) |
  | 미확정 코드 | "BPR 라인 중 한 곳", "저녁 근무", "오후조", "공급사는 A나 B" |
  | 질의 내 번복 | "44.2%라고 했는데 54.2%였나" |
  | 기준 없는 참조 | "평소랑 비슷한 조건" (참조할 기준값이 없으므로 해당 값 `null`, A06) |

  <!-- [수정] 2026-10-22: 골든 셋 A06·A07에 쓰인 "오후조", "평소랑 비슷한 조건"을 예시에 추가 -->

- **유효값 검증**: 값을 추출한 뒤 범위·허용값 검증에서 걸러지면 `status`는 `invalid_input`이 되고 `missing_fields`는 비웁니다 (I01~I05). 허용값에 없는 코드(`LINE-BPR-03`, `SIM-SUP-D`)는 비슷한 값으로 치환하지 않습니다.
- **경계값**: `fixture_alignment_offset_mm = 0`, `tool_wear_pct = 100`은 유효합니다 (C10). 이 값들은 관측 범위 밖이지만 유효값 제약 안입니다.
- **표기 정규화** <!-- [추가] 2026-10-22: 골든 셋 C03에서 쓰이는데 문서에 없던 규칙을 명시 -->
  - 범주형 코드는 대소문자를 가리지 않고 대문자로 정규화합니다 (`line-bpr-01` → `LINE-BPR-01`, `sim-sup-c` → `SIM-SUP-C`). 정규화 후에도 허용값에 없으면 `invalid_input`입니다.
  - 근무조 표현 변환: "주간조"·"day shift" → `DAY`, "밤 근무"·"야간조"·"night shift" → `NIGHT`. "저녁 근무"·"오후조"는 모호한 값입니다.
  - 한글 단위 인식: "퍼센트" → %, "마이크로미터" → µm, "밀리" → mm (C03).
- **단위 환산**: 코팅 두께만 mm → µm으로 환산하고(×1000), 지그 정렬 오차는 mm 그대로 유지합니다 (C04).
  - 반올림: 환산 결과에 `98.39999…` 같은 부동소수점 오차가 생길 수 있어, 추출 후 모든 실수 필드를 소수점 6자리로 반올림합니다(`aihub/pipeline.py`의 `QueryExtractor._coerce`). <!-- [수정] 2026-10-22: 반올림 구현 반영 (이전: 추정·미결) -->
- **비교 질의**: 레코드 여러 개로 분리하고 공통 조건은 각 레코드에 복제합니다. 공통으로 누락된 필드는 모든 레코드에서 `null`입니다 (C07, C08, P06).
- **관측 범위의 의미**: 유효값 제약이 없는 수치 필드(수량, 습도, 품질점수, 코팅 두께, 용접 에너지, 설정 편차, 정비 경과일)의 관측 범위는 참고용이며 검증 기준이 아닙니다. 다만 코드는 관측 범위와 별개로 [현재 코드의 추가 검사](#현재-코드의-추가-검사-사양-아님) 범위를 차단합니다. 이 범위를 사양으로 확정할지는 [`architecture.md`](./architecture.md)의 미결 사항에서 관리합니다.

## 응답 형식

- 엔드포인트 URL은 환경변수 `ai_hub_endpoint_url`로 지정합니다. pydantic-settings는 기본적으로 환경변수 이름의 대소문자를 구분하지 않으므로 `AI_HUB_ENDPOINT_URL`과 같은 설정입니다 (`aihub/config.py`, 출처: https://docs.pydantic.dev/latest/concepts/pydantic_settings/#case-sensitivity).
- 응답은 `data` 키 아래에 있으며, 결함률은 `prediction(defect_rate_pct)` 컬럼(단위 %)으로 반환됩니다. 값은 이미 퍼센트입니다(예: `1.65` = 1.65%, C01 실측 `1.6498678908`).

## 변경 이력

- 2026-10-22 (문서 변경, 로직 변경 없음): 코드의 추가 범위 검사 절 추가, 반올림(실수 6자리) 구현 반영, 예측값 퍼센트 단위 예시 추가.
- 2026-10-22 (문서 변경, 로직 변경 없음): 골든 셋 경로를 `data/golden_set_v2.json`으로 수정. `missing_fields` 구성 규칙(N05: 12개 전체), 예측 의도 판단 기준, 표기 정규화(대소문자·한글 단위), 모호 예시("오후조", "평소랑 비슷한 조건"), 단위 환산 시 부동소수점 주의, 환경변수 대소문자 설명을 추가.