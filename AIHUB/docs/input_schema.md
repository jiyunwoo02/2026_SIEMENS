# 입력 필드 정의 (Input Fields)

결함률 예측 엔드포인트에 전달되는 입력 필드 12개에 대한 설명입니다.
골든 셋(`golden_set.json`)의 값 범위와 케이스 `note`에 적힌 규칙을 근거로 정리했으며, 설명은 필드명과 데이터에서 추론한 내용입니다.

## 필드 목록

| # | 필드 | 타입 | 단위 | 설명 | 골든 셋 관측값 / 비고 |
|---|---|---|---|---|---|
| 1 | `production_line` | string | - | 생산 라인 코드 | `LINE-BPR-01`, `LINE-ASM-02`, `LINE-WLD-03`, `LINE-ASM-05` |
| 2 | `shift` | string | - | 근무조 (주간/야간). 질의의 "주간조", "야간"은 코드로 변환 | `DAY`, `NIGHT` |
| 3 | `supplier_code` | string | - | 입고 자재 공급사 코드 | `SIM-SUP-A`, `SIM-SUP-B`, `SIM-SUP-C` |
| 4 | `planned_quantity` | int | 개 | 생산 예정 수량 | 400 ~ 1,200 |
| 5 | `ambient_humidity_pct` | float | % | 작업장 습도 | 38.2 ~ 72.0 |
| 6 | `incoming_material_quality_score` | float | 점 | 입고 자재 품질점수 | 76.5 ~ 91.4 |
| 7 | `coating_target_thickness_um` | float | µm | 코팅 목표 두께 | 65.0 ~ 110.0. 질의가 mm이면 ×1000으로 환산 (예: 0.08mm → 80.0) |
| 8 | `weld_energy_setting_pct` | float | % | 용접 에너지 설정값 | 88.1 ~ 95.3 |
| 9 | `fixture_alignment_offset_mm` | float | mm | 지그(고정구) 정렬 오프셋. 음수 가능 | -0.045 ~ 0.28. 단위 변환 없이 mm 그대로 유지 |
| 10 | `process_setting_deviation_pct` | float | % | 공정 설정 편차 | 4.2 ~ 21.4 |
| 11 | `tool_wear_pct` | float | % | 공구 마모도 | 14.41 ~ 140.0. 유효 범위는 0~100이며 140은 G10 오류 케이스용 값 |
| 12 | `days_since_maintenance` | int | 일 | 마지막 정비 후 경과일 | 12 ~ 150 |

## 공통 규칙

- **값이 없는 경우**: 질의에서 수치를 알 수 없으면 해당 필드를 `null`로 두고 `missing_fields`에 필드명을 넣으며, `status`는 `need_more_info`가 됩니다.
- **상대 표현**: "평소보다 높다", "꽤 닳았다" 같은 표현은 수치화하지 않고 `null`로 둡니다 (G09).
- **범위 검증**: 값을 추출한 뒤 범위 검증에서 걸러지면 `status`는 `invalid_input`이 됩니다 (G10, `tool_wear_pct` 140%).
- **단위 환산**: 코팅 두께만 mm → µm으로 환산하고, 지그 정렬 오프셋은 mm 그대로 유지합니다 (G11).
- **관측값의 의미**: 관측 범위는 골든 셋에 나온 값일 뿐 스키마상의 허용 범위가 아닙니다. 범위가 명시된 것은 `tool_wear_pct`(0~100)뿐이므로, 나머지 필드의 허용 범위와 `production_line`, `shift`, `supplier_code`의 전체 허용 코드는 별도 확인이 필요합니다.

## 응답 형식

- 엔드포인트 URL은 환경변수 `ai_hub_endpoint_url`로 지정합니다.
- 응답은 `data` 키 아래에 있으며, 결함률은 `prediction(defect_rate_pct)` 컬럼(단위 %)으로 반환됩니다.