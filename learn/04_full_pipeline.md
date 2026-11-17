# 전체 파이프라인

AI Studio → AI Hub → Panopticon의 세 도구가 어떻게 연결되어 하나의 ML 서비스를 만드는지 설명합니다.

---

## 1. 전체 흐름 요약

```
[AI Studio]                 [AI Hub]                  [Panopticon]
────────────────────────    ────────────────────────   ──────────────────────────
1. 데이터 불러오기          4. 배포 프로세스 등록       7. 데이터테이블 생성
   (.rmhdf5table / CSV)        (스냅샷)                   (TEXT + Python Transform)

2. 모델 학습                5. 엔드포인트 생성          8. 위젯 배치
   (GBT / LightGBM)            REST API URL               (슬라이더, 드롭다운,
   (.rmmodel / .rmtabmod)                                   TextBox)

3. 배포 프로세스 작성       6. 클라이언트가 HTTP        9. 파라미터 연결
   (.rmp)                      요청으로 예측 호출            (슬라이더 → 파라미터
                                                              → 스크립트 치환)

                                                        10. 대시보드 완성
                                                            (.exz 내보내기)
```

---

## 2. hd-modeling 파이프라인 (공정 결함 예측)

> **참고 프로젝트**: `hd-modeling/`, `defect-dashboard/`

### 단계별 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            AI Studio                                    │
│                                                                         │
│  [데이터]                   [학습 프로세스]            [모델]             │
│  ICX_train_*.rmhdf5table ─→ GBT 회귀 학습 ──────────→ regression-v0.2   │
│  defect_pred_input         GBT 분류 학습 ──────────→ classification-v0.3│
│                                                                         │
│  [배포 프로세스]                                                         │
│  deploy.rmp           ← 회귀 모델 로드 + 외부 입력 적용                  │
│  deploy-optimization.rmp ← 분류 모델 + Prescriptive Analytics           │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ 스냅샷 배포
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              AI Hub                                     │
│                                                                         │
│  POST /services/defect_rate_pred/deploy                                 │
│    입력: {"data": [{12개 공정 변수}]}                                    │
│    출력: {"data": [{..., "prediction(defect_rate_pct)": 1.65}]}         │
│                                                                         │
│  GET  /services/defect_flag_classification/deploy-optimization?target=1 │
│    출력: {"data": [{12개 최적 조건, "confidence(1)": 0.02, ...}]}        │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ Python Transform이 HTTP 호출
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            Panopticon                                   │
│                                                                         │
│  대시보드 1: 공정 데이터 결함률 예측 플랫폼                              │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │ 슬라이더 9개 (수치형) + 드롭다운 3개 (범주형)             │            │
│  │        ↓ 파라미터 치환                                   │            │
│  │ ML_model 데이터테이블 (Python Transform → POST)          │            │
│  │        ↓                                                 │            │
│  │ 결과: 예측 결함률(%) + 등급 (TextBox Data mode)           │            │
│  └─────────────────────────────────────────────────────────┘            │
│                                                                         │
│  대시보드 2: 최적 공정조건 추천 시스템                                   │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │ 드롭다운 1개 (target: 개선/위험)                          │            │
│  │        ↓                                                 │            │
│  │ OPT_model 데이터테이블 (Python Transform → GET)          │            │
│  │        ↓                                                 │            │
│  │ 결과: 최적 공정조건 12개 (HorizontalTable)                │            │
│  └─────────────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. nice-modeling 파이프라인 (신용평가)

> **참고 프로젝트**: `nice-modeling/`, `nice-modeling/visualization/`

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            AI Studio                                    │
│                                                                         │
│  학습 데이터 (875,624행, 피처 47개)                                      │
│       ↓                                                                 │
│  LightGBM Extension (lightgbm:lightgbm 오퍼레이터)                      │
│  하이퍼파라미터: num_leaves=8, lr=0.005, scale_pos_weight=240 등         │
│       ↓                                                                 │
│  261109_ext_lightgbm.rmtabmod                                           │
│       ↓                                                                 │
│  스코어링 프로세스 (.rmp):                                               │
│    Apply Model → Generate Attributes (신용점수 공식 적용)               │
│    Score = max(0, min(1000, round(640 + 115.44 × log(conf(0)/conf(1)))))│
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ LightGBM Extension으로 Python 없이 배포
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              AI Hub                                     │
│                                                                         │
│  POST /services/nice-scoring/deploy_scoring_process_v02                 │
│    입력: {"data": [{KEY, 피처47개}]}                                     │
│    출력: {"data": [{..., "Score": 750, "confidence(1)": 0.03,           │
│                    "confidence(0)": 0.97, "prediction(TARGET)": "0"}]}  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            Panopticon                                   │
│                                                                         │
│  슬라이더 47개 (범위 0~10)                                               │
│       ↓ 파라미터 치환                                                   │
│  DataTable1 (Python Transform → POST)                                   │
│       ↓                                                                 │
│  출력: 신용점수 / 불량확률 / 정상확률 / target 예측 / 판정 / 등급구간     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 도구 간 역할 분담 정리

| 작업 | 담당 도구 |
|------|----------|
| 데이터 전처리 (필터, 컬럼 선택, 역할 지정) | AI Studio |
| 모델 학습 (GBT, LightGBM, Grid 탐색) | AI Studio |
| 배포용 프로세스 설계 | AI Studio |
| 모델 → REST API 변환 및 서빙 | AI Hub |
| 버전 관리 (스냅샷) | AI Hub |
| 사용자 입력 UI (슬라이더, 드롭다운) | Panopticon |
| REST API 호출 (Python Transform) | Panopticon |
| 결과 시각화 (TextBox, Table) | Panopticon |

---

## 5. 이 프로젝트의 AI Hub 소비자들

AI Hub 엔드포인트는 Panopticon 외에도 여러 Python 프로젝트에서 직접 호출합니다.

```
                    ┌─────────────────────────────────┐
                    │           AI Hub                │
                    │  POST /defect_rate_pred/deploy  │
                    │  GET  /.../deploy-optimization  │
                    └──────────────┬──────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
   │ defect-predictor│  │ defect-advisor  │  │ defect-dashboard │
   │                 │  │                 │  │  (Panopticon)    │
   │ Python 챗봇     │  │ Python 챗봇     │  │                 │
   │ 슬롯 필링       │  │ 슬롯 필링 +     │  │ Python Transform│
   │ → POST 예측     │  │ 최적화 의도 분류│  │ → POST / GET    │
   │                 │  │ → POST + GET    │  │                 │
   └─────────────────┘  └─────────────────┘  └─────────────────┘
              │
              ▼
   ┌─────────────────┐
   │ agent-learning  │
   │                 │
   │ Tool Calling /  │
   │ MCP / ReAct     │
   │ → POST 예측     │
   └─────────────────┘
```

**포인트**: AI Hub는 모든 클라이언트에게 동일한 REST API를 제공합니다. Panopticon이든, Python 챗봇이든, AI Agent든 호출 방식만 다를 뿐 같은 엔드포인트를 씁니다.

---

## 6. 체크리스트: 파이프라인 구축 순서

새 ML 서비스를 처음부터 구축할 때 따르는 순서입니다.

### AI Studio 단계

- [ ] 학습 데이터 준비 (.rmhdf5table 또는 CSV)
- [ ] 학습 프로세스 작성 (오퍼레이터 연결, 하이퍼파라미터 범위 설정)
- [ ] Grid 탐색으로 최적 파라미터 확인
- [ ] 모델 저장 (Write Model → `.rmmodel` 또는 `.rmtabmod`)
- [ ] 배포 프로세스 작성 (외부 입력 → Apply Model → 결과 반환)
- [ ] 배포 프로세스 테스트 실행

### AI Hub 단계

- [ ] AI Hub에 서비스 생성
- [ ] 배포 프로세스 스냅샷 등록
- [ ] 배포(Deploy) 실행
- [ ] 엔드포인트 URL 확인
- [ ] curl 또는 Python으로 엔드포인트 동작 테스트

### Panopticon 단계

- [ ] Python Transform 서버(uvicorn) 기동 확인
- [ ] 데이터테이블 생성 (TEXT 소스 + Python Transform)
  - [ ] TEXT 헤더: 변수명 목록
  - [ ] TEXT 값 행: `{P_변수명}` 자리 표시자
  - [ ] Python 스크립트: 파라미터 → JSON 조립 → API 호출 → `table = df`
  - [ ] 스키마: 출력 컬럼 타입 선언 (NUMERIC / TEXT / TIME)
  - [ ] 파라미터: 각 변수의 이름(`P_`+컬럼명), 기본값, 타입
- [ ] 위젯 배치
  - [ ] 슬라이더 (DashboardParameterName → 파라미터 연결)
  - [ ] 드롭다운 (선택지 데이터테이블 연결)
  - [ ] 결과 TextBox (Data mode, columnname 지정)
- [ ] 가져오기 테스트 (.exz 내보내기 → 가져오기)
- [ ] 슬라이더 조작 → API 호출 → 결과 갱신 확인

---

## 7. 자주 발생하는 오류와 해결

| 오류 | 원인 | 해결 |
|------|------|------|
| `java.net.ConnectException: localhost:9090` | Python Transform 서버 미기동 | uvicorn 서버 별도 기동 |
| `UnrecognizedPropertyException: isDataExportEnabled` | workbook.json에 허용되지 않는 키 포함 | 허용 19개 키로 교체 |
| `InvalidFormatException: "REAL" in ColumnType` | 컬럼 타입에 `REAL` 사용 | `REAL` → `NUMERIC` |
| `Aggregate binding failed: bad type` | TextBox 가중치 컬럼이 텍스트형 | 가중치 컬럼을 숫자형으로 변경 |
| `.exz` 가져오기 버전 오류 | server_version.txt 버전 불일치 | 세 곳의 버전 문자열 교체 후 재압축 |
| 최적화 결과 미출력 (200 OK인데 Empty) | target 파라미터 미전달 또는 Items 미설정 | 스크립트에서 P_target 파라미터 받기 + 테이블 Items 드래그 설정 |
| AI Hub 배포 후 내부 오류 | 배포 프로세스 내 데이터 경로가 절대 경로 | Repository 상대 경로로 변경 |
