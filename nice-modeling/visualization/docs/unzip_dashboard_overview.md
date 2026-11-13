# unzip_dashboard 폴더 구조 개요

판옵티콘(Panopticon) 대시보드 익스포트 파일(`261112_final_dashboard.exz`)을 압축 해제한 결과물이다.

---

## 폴더 트리

```
unzip_dashboard/
├── server_version.txt
├── DataLibrary/
│   └── datatables/              # (비어 있음)
└── Workbooks/
    └── NICE____/                # 원본: "NICE평가정보" (맹글링)
        └── 261111_UI_______Workbook/  # 원본: "261111_UI수정_게이지 Workbook" (맹글링)
            ├── workbook.json
            ├── workbook.serde.version
            ├── metadata.json
            ├── dashboards.list
            ├── datatables.list
            ├── resources.set
            ├── mangling.txt
            ├── theme.json
            ├── dashboards/
            │   └── Dashboard1.json
            ├── datatables/
            │   └── a26709f9-3c0f-4fa6-904f-cb3ab7d34552.json
            └── resources/
                └── thumbnail.png
```

---

## 파일별 설명

### `server_version.txt`

판옵티콘 서버 버전 정보를 담은 텍스트 파일.

```
2609.1.0.36042
```

### `DataLibrary/datatables/`

서버 공유 DataLibrary의 데이터테이블 저장 디렉토리. 현재 비어 있으며, 이 대시보드는 워크북 로컬 DataTable만 사용한다.

---

### `Workbooks/NICE____/`

판옵티콘은 한글 등 비ASCII 문자가 포함된 디렉토리 이름을 익스포트 시 ASCII로 맹글링한다. `mangling.txt`가 원본 이름과 맹글링된 이름 간의 매핑을 기록한다.

| 맹글링된 이름 | 원본 이름 |
|---|---|
| `NICE____` | `NICE평가정보` |
| `261111_UI_______` | `261111_UI수정_게이지` |

---

### `metadata.json`

워크북 고유 ID와 버전 정보.

| 항목 | 값 |
|---|---|
| WorkbookId | `311117ee-adcb-46a6-844c-f039cab334f3` |
| Version | `2609.1.0.36042` |

---

### `workbook.serde.version`

워크북 직렬화 포맷 버전. 현재 `V1`.

---

### `workbook.json`

워크북 최상위 설정 파일. 대시보드 목록, 글로벌 필터, 파라미터 기본값, 리포트 설정 등을 정의한다.

주요 설정:
- 글로벌 필터: 리셋 버튼·검색 필드 비활성화
- 파라미터 수용 모드: `ACCEPT_GLOBAL`
- PDF 리포트 설정: DPI 120, 페이지 996×1404 px, 마진 20
- 더블클릭 모드: `DRILL`

---

### `dashboards.list`

워크북에 포함된 대시보드 이름 목록.

```
Dashboard1
```

---

### `dashboards/Dashboard1.json`

대시보드의 모든 레이아웃·컴포넌트·파라미터를 정의하는 핵심 파일.

#### 대시보드 개요

- **제목**: `NICE평가정보: 신용점수 산출 대시보드`
- **목적**: CB(신용정보원) 변수 값을 슬라이더로 조작하여 ML 모델 엔드포인트를 실시간 호출하고 신용점수(Score)와 등급(Grade)을 확인

#### 파라미터 (슬라이더 입력 변수)

총 47개의 숫자형 파라미터가 정의되어 있으며, 대시보드 상에서 `NumericActionSlider` 컴포넌트로 표시된다. 범위는 모두 0–10이다.

| 접두사 | 변수 그룹 | 대표 변수 | 개수 |
|---|---|---|---|
| `CBINQ` | 신용정보원(CB) 조회 횟수 | `R1_CBINQ_CNT05`, `R1_CBINQ_CNT10_CD` 등 | 10 |
| `INQPTN` | 조회 패턴 | `R1_INQPTN_1Y_FN_03_FN` 등 | 7 |
| `CPCBLA` | CB 잔액 | `R1_CPCBLA_CNT05`, `R1_CPCBLA_CNT05_CL` | 2 |
| `L*` | 대출 관련 | `R1_L24003800` | 1 |
| `ZS*` | Z-score | `R1_ZS0000187` | 1 |
| `PS*` | 개인 점수 | `R1_PS0001190`, `R1_PS0001728` | 2 |
| `LA*` | 대출 금액 | `R1_LA0100016` ~ `R1_LA0400005` | 4 |
| `C*` | 카드 | `R1_C00000151`, `R1_C11061100` | 2 |
| `SC*` | 신용카드 | `R1_SC0301005` 등 | 4 |
| `LC*` | 대출 카운트 | `R1_LC0000001` ~ `R1_LC3600001` | 10 |
| `CF*` | 카드 금액 | `R1_CF0100122` 등 | 5 |
| `CL*` | 카드 한도 | `R1_CL1200915` | 1 |

#### 화면 구성

- **TextBox**: 대시보드 제목 표시 (상단, 굵은체 22pt, 배경색 `#dcdce0`)
- **NumericActionSlider × 50**: 파라미터 입력 슬라이더 (5열 배치, 각 열 10개)

---

### `datatables.list`

워크북에 포함된 DataTable의 UUID 목록.

```
a26709f9-3c0f-4fa6-904f-cb3ab7d34552
```

---

### `datatables/a26709f9-3c0f-4fa6-904f-cb3ab7d34552.json`

DataTable1의 전체 정의 파일. 데이터소스 플러그인, Transform, 스키마가 모두 포함된다.

#### 데이터소스

- 플러그인: `TEXT` (인라인 텍스트 데이터)
- 슬라이더 파라미터 값을 CSV 형태로 단일 행 데이터로 구성하여 Python Transform에 전달

#### Python Transform

판옵티콘 Python Transform 기능을 사용하여 외부 ML API를 호출한다.

- **엔드포인트**: `https://mlops.nice.plda-cloud.com/webapi/DEFAULT/api/v1/services/nice-scoring/deploy_scoring_process_v02`
- **방식**: `POST` (JSON 바디)
- 슬라이더로 입력된 47개 CB 변수를 JSON으로 묶어 엔드포인트에 전송
- 응답에서 `Score`, `prediction(TARGET)`, `confidence(0/1)` 추출

#### 파생 컬럼 (Python에서 계산)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `Score` | Numeric | ML 모델이 반환한 신용점수 |
| `Grade` | Text | 점수 구간에 따른 등급 |
| `Result` | Text | `prediction(TARGET)` 기반 정상/불량 분류 |
| `prediction(TARGET)` | Text | 모델 예측값 (0: 정상, 1: 불량) |
| `confidence(0)` | Numeric | 정상 클래스 확률 |
| `confidence(1)` | Numeric | 불량 클래스 확률 |

#### 신용점수 등급 기준

| 등급 | 점수 범위 |
|---|---|
| 최우수 | 900 이상 |
| 우수 | 800 ~ 899 |
| 양호 | 700 ~ 799 |
| 보통 | 600 ~ 699 |
| 주의 | 500 ~ 599 |
| 위험 | 500 미만 |

#### 캐시 설정

- 캐싱 활성화, 갱신 주기: 900초 (15분)
- 최대 행 수: 100,000

---

### `theme.json`

대시보드 색상 테마 파일. 판옵티콘 기본 팔레트 전체가 포함되어 있으며, 별도 커스텀 테마는 적용되지 않은 것으로 보인다.

포함된 주요 팔레트:
- **수치형(Diverging)**: Red-White-Blue, Red-White-Green, Orange-White-Blue 등
- **순차형(Sequential)**: White-Blue, White-Red, White-Green 등
- **범주형(Text)**: Twenty Eight Colors, Seven Standard Colors, Panopticon BI 등
- **단색(Constant)**: Medium Blue, Medium Red, Medium Green 등

---

### `resources.set`

워크북에 포함된 리소스 파일 목록.

```
image/png;thumbnail.png
```

### `resources/thumbnail.png`

판옵티콘 대시보드 갤러리 및 익스포트 목록에서 미리보기로 표시되는 썸네일 이미지.

---

## 데이터 흐름 요약

```
사용자 (슬라이더 조작)
        ↓
  47개 파라미터 (P_R1_*)
        ↓
  DataTable TEXT 플러그인
  (파라미터 → CSV 1행)
        ↓
  Python Transform
  (requests.post → ML API)
        ↓
  mlops.nice.plda-cloud.com
  /api/v1/services/nice-scoring/deploy_scoring_process_v02
        ↓
  응답: Score, prediction(TARGET), confidence
        ↓
  Grade 계산 (Python)
  Result 계산 (정상/불량)
        ↓
  대시보드 시각화
```
