# HD_결함률 Panopticon 대시보드 작업 내용

생성일: 2026-11-03  
참고 파일: `HT_목상해\HT_목상해\04 Panopticon\HT_목상해.exz`  
생성 스크립트: `C:\Users\z005cm2w\scripts\create_hd_exz_v2.py`

---

## 현재 상태

| 항목 | 상태 |
|------|------|
| EXZ 파일 생성 | 완료 |
| Panopticon 가져오기 | 완료 — 대시보드 2개 정상 표시 |
| API 연결 (ConnectException) | 완료 — Python 서버 기동으로 해결 |
| 결함률 예측 대시보드 | 완료 — 예측값 정상 출력 |
| 최적 공정조건 추천 대시보드 | 완료 — 최적화 결과 정상 출력 |
| Python 서버 자동화 | 완료 — start.bat에 uvicorn 자동 기동 추가 |

---

## 생성된 파일

| 버전 | 파일 경로 | 설명 |
|------|-----------|------|
| v0.1 | `HD_결함률\04 Panopticon\HD_결함률.exz` | 스크립트 자동 생성 초기본 |
| v0.2 | `HD_결함률\04 Panopticon\HD_결함률_v0.2.exz` | Panopticon UI에서 직접 수정한 버전 — 최적화 결과 테이블 컬럼 구성, defect_level 제거 등 반영 |

---

## EXZ 파일 구조

```
HD_결함률.exz (ZIP)
├── server_version.txt                     — Panopticon 버전 (24.0.0.33210)
├── Workbooks/~su/HD/HD_____Workbook/
│   ├── workbook.json                      — 워크북 컨테이너 (19개 키)
│   ├── metadata.json                      — 워크북 ID, 버전
│   ├── theme.json                         — 테마 (5개 키)
│   ├── mangling.txt                       — 대시보드 파일명 매핑
│   ├── datatables.list                    — 데이터테이블 UUID 목록
│   ├── dashboards.list                    — 대시보드 이름 목록
│   ├── resources.set                      — 리소스 목록
│   ├── workbook.serde.version             — V1
│   ├── datatables/
│   │   ├── a1b2c3d4-…ef1234567890.json   — ML_model (회귀 예측)
│   │   ├── b2c3d4e5-…f12345678901.json   — OPT_model (최적화)
│   │   ├── c3d4e5f6-…123456789012.json   — production_line_list
│   │   ├── d4e5f6a7-…234567890123.json   — shift_list
│   │   ├── e5f6a7b8-…345678901234.json   — supplier_code_list
│   │   └── f6a7b8c9-…456789012345.json   — target_list
│   └── dashboards/
│       ├── __________________.json        — 대시보드 1: 결함률 예측 플랫폼
│       └── _______________.json           — 대시보드 2: 최적 공정조건 추천
├── Data/                                  — (빈 폴더)
└── DataLibrary/datatables                 — (빈)
```

---

## 대시보드 구성

### 대시보드 1: 공정 데이터 결함률 예측 플랫폼

AI Hub 회귀 엔드포인트에 12개 공정 변수를 전송하고 결함률(%)을 예측한다.

#### 레이아웃 (39개 파트)

```
top 0.00–0.06 | 헤더: "공정 데이터 결함률 예측 플랫폼" (전체 폭)
top 0.06–0.08 | 입력/출력 섹션 레이블 + 세로 구분선 (left=0.21)
-----------------------------------------------------------------
              | Col A (0.22)           | Col B (0.47)        | Col C (0.72)
top 0.10      | 계획 생산수량 슬라이더  | 용접 에너지 슬라이더  | 경과일 슬라이더
top 0.20      | 작업장 습도 슬라이더   | 지그 오프셋 슬라이더  | 생산라인 드롭다운
top 0.30      | 자재 품질점수 슬라이더 | 공정 편차 슬라이더   | 교대조 드롭다운
top 0.40      | 코팅 두께 슬라이더    | 공구 마모율 슬라이더  | 공급사 드롭다운
-----------------------------------------------------------------
top 0.82–0.93 | 결함률 예측 출력 영역
              |   "예측 결함률 (%) :" + [prediction(defect_rate_pct)] TextBox (Data mode)
              |   "등급 :"            + [defect_level] TextBox (Data mode)
```

#### 데이터테이블: ML_model

| 항목 | 내용 |
|------|------|
| UUID | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| 플러그인 | TEXT + Python Transform |
| 엔드포인트 | POST `.../defect_rate_pred/deploy` |
| 입력 파라미터 | 12개 (NUMERIC 9개 + TEXT 3개) |
| 출력 컬럼 | `prediction(defect_rate_pct)`, `defect_level` |

#### 파라미터 목록

| 파라미터명 | 위젯 | 범위 / 선택지 | 기본값 |
|-----------|------|--------------|--------|
| P_planned_quantity | NumericActionSlider | 440–561 | 500 |
| P_ambient_humidity_pct | NumericActionSlider | 28–86 | 52.0 |
| P_incoming_material_quality_score | NumericActionSlider | 70.8–99 | 80.0 |
| P_coating_target_thickness_um | NumericActionSlider | 62–121 | 80.0 |
| P_weld_energy_setting_pct | NumericActionSlider | 76–118 | 100.0 |
| P_fixture_alignment_offset_mm | NumericActionSlider | 0.02–1.6 | 0.10 |
| P_process_setting_deviation_pct | NumericActionSlider | 0.05–16 | 0.0 |
| P_tool_wear_pct | NumericActionSlider | 2–83.9 | 45.0 |
| P_days_since_maintenance | NumericActionSlider | 1–60 | 10 |
| P_production_line | ActionDropDown | LINE-BPR-01 / LINE-BPR-02 | LINE-BPR-01 |
| P_shift | ActionDropDown | DAY / NIGHT | DAY |
| P_supplier_code | ActionDropDown | SIM-SUP-A / B / C | SIM-SUP-B |

#### 등급 판정 로직 (Python Transform 내)

```python
if defect_rate_pct < 3.0:   level = "양호 (Good)"
elif defect_rate_pct < 7.0: level = "주의 (Warning)"
else:                        level = "불량 (Poor)"
```

---

### 대시보드 2: 최적 공정조건 추천 시스템

AI Hub 최적화 엔드포인트에 target을 전송하고 최적 공정조건 1세트를 반환한다.

#### 레이아웃 (6개 파트)

```
top 0.00–0.06 | 헤더: "최적 공정조건 추천 시스템"
top 0.06–0.10 | 안내 텍스트
top 0.10–0.22 | target 드롭다운 (0=위험조건 / 1=개선조건)
top 0.22–0.28 | "최적 공정조건 출력" 레이블
top 0.28–0.98 | HorizontalTable — 최적화 결과 전체 표시
```

#### 데이터테이블: OPT_model

| 항목 | 내용 |
|------|------|
| UUID | `b2c3d4e5-f6a7-8901-bcde-f12345678901` |
| 플러그인 | TEXT + Python Transform |
| 엔드포인트 | GET `.../defect_flag_classification/deploy-optimization` |
| 입력 파라미터 | P_target (TEXT: "0" 또는 "1") |
| 출력 컬럼 | 12개 입력변수 + `confidence(1)`, `confidence(0)`, `prediction(high_defect_flag)` |

---

## 엔드포인트 URL

| 용도 | URL |
|------|-----|
| 회귀 예측 (POST) | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_rate_pred/deploy` |
| 최적화 (GET) | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization` |

---

## Panopticon 가져오기 오류 이력

Jackson 역직렬화 오류가 순차적으로 발생. 오류 메시지로 내부 클래스/Enum 구조를 파악하며 수정함.

### 오류 1 — UnrecognizedPropertyException: `isDataExportEnabled` in Workbook

```
Unrecognized field "isDataExportEnabled"
(class com.panopticon.dashboards.model.Workbook)
known properties: [actionsPerDatatable, cacheSources, commitHash, dashboards,
datatables, description, doubleClickMode, globalFilters, globalFiltersAlignment,
isPublished, legacyStyle, metadata, name, parameterAssignmentMode, properties,
reportSettings, repositoryPath, showGlobalFilters, theme]
```

**원인**: `workbook.json`에 Dashboard 전용 필드(`isDataExportEnabled`, `isExportEnabled`, `settings`, `syncGroups`) 포함.  
**수정**: HT 원본의 19개 키 구조로 교체.

---

### 오류 2 — UnrecognizedPropertyException: `partStyles` in Theme

```
Unrecognized field "partStyles"
(class com.panopticon.dashboards.model.Theme)
known properties: [generalColors, style, colorPalettes, glyphPalettes, name]
```

**원인**: `theme.json`에 `partStyles` 필드 포함.  
**수정**: HT 원본의 5개 키(`colorPalettes`, `generalColors`, `glyphPalettes`, `name`, `style`)로 교체.

---

### 오류 3 — InvalidFormatException: `"REAL"` in ColumnType

```
Cannot deserialize value of type `com.panopticon.dashboards.model.ColumnType`
from String "REAL": not one of the values accepted for Enum class:
[NUMERIC, TEXT, TIME]
```

**원인**: `schema.columns.column[].type` 필드에 `"REAL"` 사용.  
**수정**: `"REAL"` → `"NUMERIC"` 변경.

---

### 오류 4 — UnrecognizedPropertyException: `designerValue` in DatatableSchemaParameter

```
Unrecognized field "designerValue"
(class com.panopticon.dashboards.model.DatatableSchemaParameter)
known properties: [defaultValue, synthesized, name, defaultValueType]
```

**원인**: `schema.parameters.parameter[]` 객체에 대시보드 파라미터 필드(`designerValue`, `valueSeparator`, `defaultValueSettings`) 포함.  
**수정**: schema 파라미터는 4개 필드(`defaultValue`, `synthesized`, `name`, `defaultValueType`)만 사용하도록 분리.

---

### 오류 5 — 상세 메시지 없이 가져오기 X 실패 (무음 실패)

4번 오류 수정 후에도 Panopticon 가져오기 시 에러 메시지 없이 X 표시만 나타남.

**원인**: ZIP 파일 내 명시적 디렉터리 엔트리 누락 + `resources/thumbnail.png` 파일 미포함.
- HT 원본은 `Workbooks/`, `Workbooks/~su/`, `HD/`, `datatables/`, `dashboards/`, `resources/` 등 디렉터리 엔트리를 명시적으로 포함
- `resources.set`에 `thumbnail.png`를 참조하지만 실제 파일이 없어 서버 측에서 NullPointerException 추정

**수정**:
- 모든 디렉터리에 ZIP 엔트리 명시 추가 (`external_attr = 0x10`)
- 1×1 픽셀 투명 PNG를 `resources/thumbnail.png`로 포함
- `DataLibrary/` 디렉터리 엔트리도 HT 원본과 동일하게 추가

**결과**: 가져오기 성공, 대시보드 2개 정상 표시됨

---

### 오류 6 — java.net.ConnectException: Failed to connect to localhost:9090

대시보드 로드 후 예측/최적화 결과 영역에 아래 오류 표시:

```
java.net.ConnectException: Failed to connect to localhost/(0:0:0:0:0:0:0:1):9090
```

**1차 시도 (실패)**: `proxies={"http": None, "https": None}` 추가
→ Java 레벨에서 소켓을 가로채기 때문에 Python `proxies` 옵션으로는 우회 불가.

**원인 파악**: HT 원본 스크립트와 비교한 결과, HT는 `verify=False`, `timeout`, `proxies` 없이 순수하게 `requests.post(url, json=data, headers=headers)` 만 사용. `verify=False` 사용 시 Panopticon이 SSL 처리를 위해 내부 프록시(localhost:9090)로 라우팅하는 것으로 추정.

**수정**: HT 원본 패턴과 동일하게 단순화.

```python
# 변경 전 (실패)
requests.post(endpoint_url, json=json_data, verify=False, timeout=30, proxies=NO_PROXY)

# 변경 후 (HT 원본 방식)
headers = {'Content-Type': 'application/json'}
requests.post(endpoint_url, json=json_data, headers=headers)
requests.get(endpoint_url,  params={"target": str(target_val)}, headers=headers)
```

**결과**: 여전히 동일한 오류 발생 → 스크립트 코드 문제가 아님으로 확인

---

### 오류 6 최종 해결 — Python Transform 서버(uvicorn) 수동 기동

**원인 확정**: `Panopticon.properties`에 Python 서버 주소는 이미 올바르게 설정되어 있었으나, 해당 포트(9090)에서 실제로 실행 중인 Python 서버 프로세스가 없었음.

```
connector.python.host=localhost
connector.python.mode=fast_api
connector.python.port=9090
```

**해결**:

1. 필요 패키지 설치:
   ```powershell
   pip install fastapi uvicorn pandas serpent requests
   ```

2. Python 서버 기동:
   ```powershell
   cd "C:\Users\z005cm2w\Downloads\Panopticon_2609\Panopticon_2609\python_integration\panopticon_fastapi_py"
   uvicorn app.main:app --host 0.0.0.0 --port 9090
   ```

3. 동작 확인: `http://localhost:9090/` → `{"Hello":"World"}` 응답 확인

**결과**: ConnectException 해소, Python Transform 정상 동작

---

### 오류 7 — No module named 'requests'

Python Transform 실행 시 `java.lang.RuntimeException: No module named 'requests'` 발생.

**원인**: uvicorn 서버가 실행 중인 Python 환경에 `requests` 패키지 미설치.

**해결**:
```powershell
pip install requests
```
uvicorn 재시작 후 해소.

---

### 오류 8 — 최적 공정조건 추천 결과 미출력

Python 서버 로그에 `200 OK`가 찍히지만 대시보드에 결과가 표시되지 않음.

**원인 1**: `target_val = '0'` 하드코딩 — 대시보드 `P_target` 파라미터가 API에 전달되지 않음.

**원인 2**: API 응답 파싱 코드가 주석 처리 상태로 `table`이 갱신되지 않음.

**API 응답 구조 확인**:
```
=== API RESPONSE KEYS === ['data']
result["data"] → 최적 공정조건 1행 (12개 변수 + confidence(0), confidence(1), prediction)
```

**최종 수정 코드** (OPT_model Python Transform):
```python
import pandas as pd
import requests

headers = {'Content-Type': 'application/json'}
endpoint_url = "https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization"

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

**결과**: `Result is DF` 로그 확인, 최적 공정조건 1세트 정상 출력.

---

### 오류 9 — 최적화 결과 테이블 Empty (Items 미설정)

데이터는 정상 반환되나 대시보드 테이블 위젯에 "Empty / Breakdown 변수 없음" 표시.

**원인**: 테이블 시각화 위젯에 표시할 컬럼이 설정되지 않은 상태.

**해결**: Panopticon UI에서 왼쪽 OPT_model 컬럼을 테이블 위젯 Items 영역으로 드래그 앤 드롭하여 표시 컬럼 구성.

**결과**: 최적 공정조건 추천 결과 정상 표시.

---

### Python 서버 자동화 — start.bat 수정

매일 오전 9시 작업 스케줄러에서 `start.bat` 실행 시 uvicorn도 함께 기동되도록 수정.

**수정 내용** (`start.bat`에 추가):
```bat
REM Start Python FastAPI server in a separate window
start "Panopticon Python Server" cmd /k "cd /d "%PANO_HOME%\python_integration\panopticon_fastapi_py" && uvicorn app.main:app --host 0.0.0.0 --port 9090"
```

Tomcat 기동 직전에 실행 → 별도 cmd 창("Panopticon Python Server")에서 uvicorn 자동 시작.

---

### 오류 6 추가 분석 — Python Transform 서버 미구동

HT 원본과 HD 생성본의 datatable JSON 구조를 전체 비교한 결과 최상위 키, datasource 키, settings 서브그룹 이름 모두 완전히 동일함이 확인됨.

**결론**: `java.net.ConnectException: Failed to connect to localhost:9090`은 Python 스크립트가 실행되기 전에 발생. Panopticon JVM이 Python Transform 실행 서버(기본 포트 9090)에 연결을 시도하다 실패하는 것으로, **Panopticon의 Python 실행 서버가 설치/구동되어 있지 않은 환경 문제**.

**확인 방법**:
1. HT_목상해 대시보드에서도 API 예측 결과가 동일하게 실패하는지 확인 → 동일 실패 시 환경 문제 확정
2. Panopticon 관리자 페이지 → `Administration > Data > Python Server` 에서 Python 서버 URL(기본: `http://localhost:9090`) 설정 여부 확인
3. Panopticon 서버에서 Python 실행 서버 프로세스 별도 기동 필요

**참고**: Altair Panopticon의 Python Transform은 Panopticon 서버와 별개로 Python 실행 데몬(Jython 또는 CPython 서버)이 동작해야 함. 이 데몬이 없으면 모든 Python Transform 데이터테이블이 동일한 Java ConnectException으로 실패함.

---

## JSON 구조 핵심 정리 (HT 원본 기준)

### workbook.json (19개 키)

`actionsPerDatatable`, `cacheSources`, `commitHash`, `dashboards`, `datatables`,
`description`, `doubleClickMode`, `globalFilters`, `globalFiltersAlignment`,
`isPublished`, `legacyStyle`, `metadata`, `name`, `parameterAssignmentMode`,
`properties`, `reportSettings`, `repositoryPath`, `showGlobalFilters`, `theme`

### theme.json (5개 키)

`colorPalettes`, `generalColors`, `glyphPalettes`, `name`, `style`

### dashboard.json (15개 키)

`actionsPerDatatable`, `autoActionMode`, `defaultRuntimeSettings`, `description`,
`globalFiltersEnabled`, `isDataExportEnabled`, `isExportEnabled`, `layout`,
`links`, `name`, `parameters`, `parts`, `resetFiltersOnParameterUpdate`,
`runtimeSettings`, `syncGroups`

### datatable.json (핵심 필드)

| 필드 | 올바른 값 |
|------|----------|
| `isCachingEnabled` | `true` |
| `refreshPeriod` | `900` |
| `status` | `"IDLE"` |

### datasource 필드

| 필드 | 올바른 값 |
|------|----------|
| `sourceColumn` | `""` (빈 문자열) |
| `linkedTableId` | `null` |
| `isMetaDatasource` | `false` |

### schema.columns.column[] — ColumnType Enum

허용값: `NUMERIC`, `TEXT`, `TIME` (대문자, `REAL` 불가)

### schema.parameters.parameter[] — DatatableSchemaParameter (4개 필드만)

`defaultValue`, `synthesized`, `name`, `defaultValueType`

### NumericDataHelper

```json
{"name": "DecimalSeparator", "value": "."}
```

---

## HT_목상해 레이아웃에서 채용한 패턴

| 패턴 | 설명 |
|------|------|
| NumericActionSlider | width=0.12, height=0.07, min/max 레이블 TextBox 쌍 |
| ActionDropDown | ColumnName + TitleColumnName + DashboardParameterName |
| TextBox Data mode | datatableName + columnname + AggregateType=Unique |
| HorizontalTable | VisibleDescriptors 생략 시 전체 컬럼 표시 |
| Python Transform | TransformSettings > Python > PythonSettings > Script |
| TEXT 데이터소스 | 1행: 컬럼명, 2행: `{P_파라미터명}` 치환값 |
| 파라미터 치환 | TEXT 타입 → 따옴표 자동 추가 / NUMERIC 타입 → 숫자 그대로 |
| 드롭다운 TEXT 콘텐츠 | 각 값 뒤에 쉼표 추가 → Field1 컬럼 자동 생성 |
