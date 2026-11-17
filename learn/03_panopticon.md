# Panopticon

Altair Panopticon은 실시간 데이터 시각화에 특화된 BI 대시보드 도구입니다.  
이 프로젝트에서는 AI Hub REST API를 호출해 ML 예측 결과를 대시보드에 실시간으로 표시하는 용도로 사용합니다.

---

## 1. 핵심 개념

### 워크북(Workbook)

여러 대시보드를 묶는 컨테이너입니다. 하나의 `.exz` 파일에 담겨 가져오기/내보내기가 가능합니다.

### 대시보드(Dashboard)

위젯(파트)들의 레이아웃을 정의하는 단위입니다. 하나의 워크북에 대시보드를 여러 개 넣을 수 있습니다.

> **참고 프로젝트**: `defect-dashboard/`의 대시보드 2개:
> - **공정 데이터 결함률 예측 플랫폼** — 슬라이더 12개 → 결함률(%) + 등급 출력
> - **최적 공정조건 추천 시스템** — target 드롭다운 → 최적 공정조건 테이블 출력

### 데이터테이블(Datatable)

외부 데이터를 가져오는 단위입니다. 하나의 데이터테이블은 하나의 데이터 소스와 그 위에 올라가는 변환(Transform)으로 구성됩니다.

### 파트(Part)

대시보드에 배치되는 위젯 하나입니다. 위치는 0~1 범위의 `top`/`left`/`height`/`width` 비율로 지정합니다.

---

## 2. 주요 위젯 종류

| 위젯 | 설명 | 주로 쓰는 상황 |
|------|------|----------------|
| `TextBox` | 텍스트 또는 데이터 값 표시 | 헤더, KPI 값, 레이블 |
| `NumericActionSlider` | 수치 입력 슬라이더 | 모델 입력 파라미터 조절 |
| `ActionDropDown` | 드롭다운 선택 | 범주형 파라미터 선택 |
| `HorizontalTable` | 행 테이블 | 최적화 결과 전체 표시 |

### TextBox 모드

| 모드 | 용도 |
|------|------|
| **Static** | 고정 문자열 표시 (헤더, 설명) |
| **Data** | 데이터테이블의 컬럼 값 표시 (예측 결과 출력) |

---

## 3. 데이터 소스 구성

### TEXT + Python Transform 패턴

이 프로젝트에서 AI Hub API를 호출하는 핵심 패턴입니다.

```
[TEXT 데이터소스]
  컬럼 헤더 행: 변수명1, 변수명2, ...
  값 행:        {P_변수명1}, {P_변수명2}, ...  ← 대시보드 파라미터로 치환됨
        │
        ▼
[Python Transform]
  파라미터가 치환된 값으로 JSON 조립 → AI Hub POST/GET 호출 → 결과 DataFrame 반환
```

**핵심 원리**: `{P_파라미터명}`은 Panopticon이 실행 시점에 대시보드 파라미터 값으로 치환합니다.  
슬라이더나 드롭다운이 바뀌면 파라미터가 갱신되고, 데이터테이블이 자동 재실행됩니다.

---

## 4. 파라미터 연결 구조

```
슬라이더(NumericActionSlider)
  └─ DashboardParameterName: "P_planned_quantity"
        │
        ▼ (값이 바뀌면 파라미터 갱신)
대시보드 파라미터: P_planned_quantity = 500
        │
        ▼ ({P_planned_quantity} 치환)
TEXT 데이터소스 → Python Transform → AI Hub 호출
```

### 슬라이더 주요 속성

| 속성 | 설명 | 예시 |
|------|------|------|
| `Minimum` / `Maximum` | 슬라이더 범위 | 440 / 561 |
| `DefaultValue` | 초기값 | 500 |
| `DashboardParameterName` | 연결할 파라미터 이름 | `P_planned_quantity` |
| `ActionPartTriggerMode` | 트리거 방식 | `Parameter` |
| `Title` | 슬라이더 라벨 | `planned_quantity` |

### 드롭다운(ActionDropDown) 주요 속성

| 속성 | 설명 |
|------|------|
| `ColumnName` | 선택지 데이터테이블의 값 컬럼 |
| `TitleColumnName` | 표시할 컬럼 (ColumnName과 같아도 됨) |
| `DashboardParameterName` | 연결할 파라미터 이름 |

드롭다운의 선택지는 별도 TEXT 데이터테이블로 관리합니다:

```
production_line_list 데이터테이블:
  Field1
  LINE-BPR-01,
  LINE-BPR-02,
```

---

## 5. Python Transform

Panopticon의 데이터테이블에서 Python 코드를 실행할 수 있는 기능입니다.  
AI Hub REST API를 호출해 결과를 데이터테이블에 돌려주는 역할을 합니다.

### 동작 방식

1. Panopticon JVM이 별도로 기동된 **Python Transform 서버**(uvicorn, 기본 포트 9090)로 스크립트를 전송합니다.
2. Python 서버가 스크립트를 실행하고 결과 DataFrame을 반환합니다.
3. `table = df` 형태로 결과를 반환합니다.

> **중요**: Python Transform을 사용하려면 Panopticon 서버와 별개로 **Python 실행 서버(uvicorn)**가 반드시 먼저 기동되어 있어야 합니다.  
> 서버가 없으면 `java.net.ConnectException: Failed to connect to localhost:9090` 오류가 발생합니다.  
> 참고: [`defect-dashboard/04 Panopticon/Panopticon_작업내용.md`](../defect-dashboard/04%20Panopticon/Panopticon_작업내용.md) 오류 6 해결 항목.

### Python Transform 서버 기동

```powershell
cd "C:\...\Panopticon_2609\python_integration\panopticon_fastapi_py"
uvicorn app.main:app --host 0.0.0.0 --port 9090
```

필요 패키지:

```powershell
pip install fastapi uvicorn pandas serpent requests
```

### Python Transform 스크립트 예시

**결함률 예측 (ML_model 데이터테이블)**:

> **참고 프로젝트**: `defect-dashboard/`

```python
import pandas as pd
import requests

headers = {'Content-Type': 'application/json'}
endpoint_url = "https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_rate_pred/deploy"

# TEXT 소스의 {P_...} 치환값이 table 딕셔너리로 들어옴
row = table[0]
json_data = {
    "data": [{
        "production_line":                   row["production_line"],
        "shift":                             row["shift"],
        "supplier_code":                     row["supplier_code"],
        "planned_quantity":                  int(row["planned_quantity"]),
        "ambient_humidity_pct":              float(row["ambient_humidity_pct"]),
        "incoming_material_quality_score":   float(row["incoming_material_quality_score"]),
        "coating_target_thickness_um":       float(row["coating_target_thickness_um"]),
        "weld_energy_setting_pct":           float(row["weld_energy_setting_pct"]),
        "fixture_alignment_offset_mm":       float(row["fixture_alignment_offset_mm"]),
        "process_setting_deviation_pct":     float(row["process_setting_deviation_pct"]),
        "tool_wear_pct":                     float(row["tool_wear_pct"]),
        "days_since_maintenance":            int(row["days_since_maintenance"]),
    }]
}

response = requests.post(endpoint_url, json=json_data, headers=headers)
response.raise_for_status()
result = response.json()

df = pd.DataFrame(result["data"])

defect_rate = float(df["prediction(defect_rate_pct)"].iloc[0])
if defect_rate < 3.0:
    level = "양호 (Good)"
elif defect_rate < 7.0:
    level = "주의 (Warning)"
else:
    level = "불량 (Poor)"

df["defect_level"] = level
table = df
```

**최적 공정조건 추천 (OPT_model 데이터테이블)**:

```python
import pandas as pd
import requests

headers = {'Content-Type': 'application/json'}
endpoint_url = "https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization"

# P_target 파라미터를 드롭다운에서 받음
try:
    target_val = str(int(P_target))
except:
    target_val = str(int(table[0]['P_target'])) if table and 'P_target' in table[0] else '1'

response = requests.get(endpoint_url, params={"target": target_val}, headers=headers)
response.raise_for_status()
result = response.json()

df = pd.DataFrame(result["data"])
table = df
```

---

## 6. `.exz` 파일 구조

Panopticon 워크북의 내보내기/가져오기 형식입니다. 실제로는 **ZIP 파일**입니다.

```
워크북.exz (ZIP)
├── server_version.txt                     — Panopticon 서버 버전
├── Workbooks/~su/<그룹>/<워크북이름>/
│   ├── workbook.json                      — 워크북 메타데이터 (19개 키)
│   ├── metadata.json                      — 워크북 ID, 버전
│   ├── theme.json                         — 색상 테마 (5개 키)
│   ├── mangling.txt                       — 한글 파일명 매핑
│   ├── datatables.list                    — 데이터테이블 UUID 목록
│   ├── dashboards.list                    — 대시보드 이름 목록
│   ├── datatables/
│   │   ├── <uuid>.json                   — 데이터테이블 정의
│   │   └── ...
│   └── dashboards/
│       ├── <대시보드이름>.json            — 대시보드 위젯/파라미터 정의
│       └── ...
├── Data/                                  — (대부분 비어 있음)
└── DataLibrary/datatables                 — 공유 데이터테이블
```

### JSON 파일 필수 키

| 파일 | 허용 키 |
|------|---------|
| `workbook.json` | `actionsPerDatatable`, `cacheSources`, `commitHash`, `dashboards`, `datatables`, `description`, `doubleClickMode`, `globalFilters`, `globalFiltersAlignment`, `isPublished`, `legacyStyle`, `metadata`, `name`, `parameterAssignmentMode`, `properties`, `reportSettings`, `repositoryPath`, `showGlobalFilters`, `theme` (19개) |
| `theme.json` | `colorPalettes`, `generalColors`, `glyphPalettes`, `name`, `style` (5개) |
| `datatable.json` schema 컬럼 타입 | `NUMERIC`, `TEXT`, `TIME` (`REAL` 불가) |
| `datatable.json` schema parameter | `defaultValue`, `synthesized`, `name`, `defaultValueType` (4개만) |

> 허용되지 않는 키가 포함되어 있으면 Panopticon 가져오기 시 `UnrecognizedPropertyException`이 발생합니다.  
> 참고: [`defect-dashboard/04 Panopticon/Panopticon_작업내용.md`](../defect-dashboard/04%20Panopticon/Panopticon_작업내용.md) 오류 1~5 항목.

---

## 7. 대시보드 레이아웃 예시

> **참고 프로젝트**: `defect-dashboard/`의 대시보드 1

```
top 0.00–0.06 | 헤더: "공정 데이터 결함률 예측 플랫폼" (전체 폭)
top 0.06–0.08 | 입력/출력 섹션 레이블 + 세로 구분선
──────────────────────────────────────────────────────────
              | Col A (left=0.00) | Col B (left=0.22) | Col C (left=0.47)
top 0.10      | 계획생산수량 슬라이더  | 용접에너지 슬라이더   | 경과일 슬라이더
top 0.20      | 작업장습도 슬라이더   | 지그오프셋 슬라이더   | 생산라인 드롭다운
top 0.30      | 자재품질점수 슬라이더 | 공정편차 슬라이더    | 교대조 드롭다운
top 0.40      | 코팅두께 슬라이더    | 공구마모율 슬라이더   | 공급사 드롭다운
──────────────────────────────────────────────────────────
top 0.82–0.93 | 예측 결함률(%) TextBox (Data mode)
              | 등급 TextBox (Data mode)
```

---

## 8. 버전 호환성

`.exz`의 `server_version.txt`와 `metadata.json`에 기록된 버전이 가져오는 서버 버전보다 높으면 가져오기가 거부됩니다.

> **참고 프로젝트**: `nice-modeling/visualization/docs/draft/Panopticon_dashboard_guide.md` §5-2

```
원본 (2609.1.0.36042) → 26.1 서버(26.1.0.35462)에서 가져오기 실패
```

**해결 방법**: `server_version.txt`와 `metadata.json`의 버전 문자열을 대상 서버 버전으로 교체 후 재압축합니다.

---

## 9. 주요 팁

- **슬라이더 이름 = 파라미터 이름 = 스크립트 `{P_...}` 자리 표시자**: 세 곳이 모두 같아야 합니다. 하나라도 다르면 값이 치환되지 않습니다.
- **TEXT 타입 파라미터**: Panopticon이 자동으로 따옴표를 추가합니다. NUMERIC 타입은 숫자 그대로 치환됩니다.
- **드롭다운 선택지 값 뒤에 쉼표**: 각 선택지 뒤에 쉼표를 붙여야 `Field1` 컬럼이 정상 생성됩니다.
- **HorizontalTable의 Items**: 테이블 위젯에 컬럼이 설정되어 있지 않으면 "Empty" 화면이 나옵니다. UI에서 컬럼을 Items 영역으로 드래그해 추가해야 합니다.
- **결과 TextBox의 가중치 컬럼**: 텍스트 컬럼 박스의 `WeightColumnName`은 반드시 숫자형 컬럼이어야 합니다. 텍스트 컬럼 자신으로 지정하면 `Aggregate binding failed` 오류가 납니다.
