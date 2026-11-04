# defect-dashboard

공정 데이터 기반 **결함률 예측** 및 **최적 공정조건 추천** Panopticon 대시보드 제작물입니다.  
Altair AI Studio (RapidMiner) · AI Hub · Panopticon 스택을 활용합니다.

---

## 대시보드 현황

| 대시보드 | 상태 |
|---|---|
| 공정 데이터 결함률 예측 플랫폼 | 완료 — 예측값 정상 출력 |
| 최적 공정조건 추천 시스템 | 완료 — 최적화 결과 정상 출력 |

---

## 아키텍처

```
[AI Studio]                   [AI Hub]                  [Panopticon]
학습 프로세스 (.rmp)      →   스냅샷 배포           →   REST API 호출
GBT 모델 생성                 엔드포인트 생성            대시보드 시각화
                              REST API 제공
```

Panopticon의 Python Transform 위젯이 AI Hub REST API를 직접 호출합니다.  
Python Transform 실행을 위해 **uvicorn 서버(포트 9090)가 별도로 기동**되어 있어야 합니다.

---

## 대시보드 1 — 공정 데이터 결함률 예측 플랫폼

슬라이더·드롭다운으로 12개 공정 변수를 입력하면 AI Hub 회귀 엔드포인트를 호출해 결함률(%)과 등급을 출력합니다.

### 입력 위젯

| 파라미터 | 위젯 | 범위 / 선택지 | 기본값 |
|---|---|---|---|
| `planned_quantity` | 슬라이더 | 440 – 561 | 500 |
| `ambient_humidity_pct` | 슬라이더 | 28 – 86 | 52.0 |
| `incoming_material_quality_score` | 슬라이더 | 70.8 – 99 | 80.0 |
| `coating_target_thickness_um` | 슬라이더 | 62 – 121 | 80.0 |
| `weld_energy_setting_pct` | 슬라이더 | 76 – 118 | 100.0 |
| `fixture_alignment_offset_mm` | 슬라이더 | 0.02 – 1.6 | 0.10 |
| `process_setting_deviation_pct` | 슬라이더 | 0.05 – 16 | 0.0 |
| `tool_wear_pct` | 슬라이더 | 2 – 83.9 | 45.0 |
| `days_since_maintenance` | 슬라이더 | 1 – 60 | 10 |
| `production_line` | 드롭다운 | LINE-BPR-01 / LINE-BPR-02 | LINE-BPR-01 |
| `shift` | 드롭다운 | DAY / NIGHT | DAY |
| `supplier_code` | 드롭다운 | SIM-SUP-A / B / C | SIM-SUP-B |

### 출력

| 항목 | 값 |
|---|---|
| 예측 결함률 | `prediction(defect_rate_pct)` (%) |
| 등급 | 양호 (< 3%) / 주의 (3–7%) / 불량 (≥ 7%) |

### 엔드포인트

```
POST https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_rate_pred/deploy
```

---

## 대시보드 2 — 최적 공정조건 추천 시스템

`target` 방향(개선 / 위험)을 선택하면 AI Hub 최적화 엔드포인트를 호출해 최적 공정 조건 1세트를 테이블로 출력합니다.

### 입력

| 파라미터 | 선택지 | 의미 |
|---|---|---|
| `target` | `1` | 불량 확률 최소화 (개선 조건 탐색) |
| `target` | `0` | 정상 확률 최소화 (위험 조건 탐색) |

### 출력

최적화된 공정 조건 12개 + `confidence(0)` / `confidence(1)` / `prediction(high_defect_flag)`

### 엔드포인트

```
GET https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization?target=0|1
```

---

## 폴더 구조

이 저장소에는 **문서**만 포함합니다. 실제 AI Studio 프로세스 파일(`.rmp`)·모델(`.rmmodel`)·데이터·Panopticon EXZ 파일은 로컬 경로에 있습니다.

```
defect-dashboard/
├── README.md                        — 이 문서
├── CLAUDE.md                        — 프로젝트 맥락 (AI Studio 구성, 데이터 스키마, 아키텍처)
├── 03 Delpoy/
│   └── endpoint_urls.md             — AI Hub 엔드포인트 URL 목록
├── 04 Panopticon/
│   └── Panopticon_작업내용.md       — EXZ 파일 구성, 오류 해결 이력 (9건), JSON 구조 정리
└── docs/
    ├── endpoint_spec.md             — 엔드포인트 요청·응답 상세 명세
    └── HD현대_대시보드_가이드.html  — 대시보드 사용 가이드 (HTML)
```

로컬 작업 경로: `C:\Users\z005cm2w\Downloads\HT_목상해\HD_결함률\`

```
HD_결함률/
├── 01 Data/        — 학습·예측용 데이터 (.rmhdf5table)
├── 02 Process/     — AI Studio 학습 프로세스 (.rmp) + 학습된 모델 (.rmmodel)
├── 03 Deploy/      — 배포 모델 + 배포 프로세스
├── 04 Panopticon/  — EXZ 파일 (v0.1, v0.2)
└── 자료/           — 참고 문서
```

---

## 모델

| 모델 | 알고리즘 | 목표 변수 | 학습 데이터 |
|---|---|---|---|
| Regression | GBT (Grid 탐색) | `defect_rate_pct` (%) | 2,400행 |
| Classification | GBT (Grid 탐색) + Prescriptive Analytics | `high_defect_flag` (0/1) | 2,040행 |

입력 변수는 공통 12개 (`production_line`, `shift`, `supplier_code` + 수치형 9개).

---

## Panopticon 실행 방법

1. **Python Transform 서버 기동** (포트 9090 — 필수):
   ```powershell
   cd "C:\...\Panopticon_2609\python_integration\panopticon_fastapi_py"
   uvicorn app.main:app --host 0.0.0.0 --port 9090
   ```
   `start.bat`에 자동 기동 구문이 추가되어 있어 Panopticon 시작 시 함께 실행됩니다.

2. **EXZ 파일 가져오기**: Panopticon UI → Import → `04 Panopticon/HD_결함률_v0.2.exz`

3. **대시보드 열기**: 워크북 `HD_결함률` → 대시보드 1 또는 2 선택

---

## 변경 이력

- **2026-11-04**: 초기 작성 — 폴더 구조, 대시보드 구성, 엔드포인트, 실행 방법 정리.
