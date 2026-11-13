# AI Studio 파일 구조 분석

AI Studio(RapidMiner)에서 생성되는 세 가지 파일 확장자(`.rmp`, `.rmmodel`, `.rmtabmod`)의 내부 구조를 분석한 문서입니다.

---

## 파일 목록

| 파일명 | 확장자 | 크기 |
|---|---|---|
| `create_lightgbm_process_v0.1.rmp` | `.rmp` | ~10KB |
| `create_lightgbm_process_v0.2.rmp` | `.rmp` | ~8KB |
| `test_scoring_process.rmp` | `.rmp` | ~12KB |
| `261106_pyl_lightgbm.rmmodel` | `.rmmodel` | ~3.8MB |
| `261109_ext_lightgbm.rmtabmod` | `.rmtabmod` | ~1.2MB |

---

## 1. `.rmp` — RapidMiner Process

### 개요

**포맷: XML**

AI Studio 캔버스에서 구성한 워크플로우 그래프를 직렬화한 파일입니다. 프로세스를 실행하는 오퍼레이터 노드, 연결 관계, 파라미터, 캔버스 메모가 모두 포함됩니다.

### 최상위 구조

```xml
<?xml version="1.0" encoding="UTF-8"?>
<process version="12.1.001">
  <context>
    <input/>
    <output/>
    <macros/>
  </context>
  <operator class="process" ...>
    <parameter key="..." value="..."/>
    <process>
      <!-- 오퍼레이터 노드들 -->
      <operator class="read_csv" .../>
      <operator class="python_learner" .../>
      <!-- 연결 관계 -->
      <connect from_op="..." to_op="..."/>
      <!-- 캔버스 메모 -->
      <description .../>
    </process>
  </operator>
</process>
```

### 주요 XML 요소

| 요소 | 역할 |
|---|---|
| `<process version="">` | RapidMiner 버전 정보 |
| `<operator class="">` | 오퍼레이터 노드 (Read CSV, Python Learner 등) |
| `<parameter key="" value="">` | 오퍼레이터별 설정값 |
| `<connect from_op="" to_op="">` | 노드 간 포트 연결 |
| `<description>` | 캔버스의 메모 박스 (HTML 엔티티 인코딩) |
| `<list key="">` | 멀티밸류 파라미터 (컬럼 목록, 역할 설정 등) |

### v0.1 vs v0.2 비교

| 항목 | v0.1 (`create_lightgbm_process_v0.1.rmp`) | v0.2 (`create_lightgbm_process_v0.2.rmp`) |
|---|---|---|
| 학습 오퍼레이터 | `python_scripting:python_learner` | `lightgbm:lightgbm` |
| 모델 저장 경로 | `261106_pyl_lightgbm` | `261109_ext_lightgbm` |
| KEY 역할 설정 | Set Role에서 KEY 제외 | KEY를 id role로 설정 |
| Python 환경 | base conda + LightGBM 4.6.0 직접 설치 | LightGBM Extension jar 사용 |

### Python Learner 오퍼레이터 내 코드 구조 (v0.1)

Python 소스코드는 `<parameter key="operator">` 값 안에 JSON + 코드 형태로 인라인 저장됩니다.

```json
{
  "name": "Custom Python Learner",
  "dropSpecial": true,
  "capabilities": ["numerical attributes", "binominal label", "polynominal label"],
  "parameters": [...],
  "inputs": [],
  "outputs": []
}
```

이후 `.import pandas as pd\n...` 형태로 Python 코드가 이어집니다. 필수 함수는 두 가지입니다.

- `rm_train(X, y, params)` : 모델 학습, dict 반환
- `rm_apply(X, container)` : 예측 수행, (prediction, probabilities) 반환

---

## 2. `.rmmodel` — Python Learner 산출 모델

### 개요

**포맷: JSON**

`python_scripting:python_learner` 오퍼레이터로 학습한 모델의 저장 파일입니다. Python pickle로 직렬화된 모델 객체를 Base64로 인코딩하여 JSON 필드에 저장합니다.

### JSON 구조

```json
{
  "rm_object_type": "com.rapidminer.extension.pythonscripting.model.PythonModel",
  "rm_object_version": "12.1.1",
  "headerExampleSet": { ... },
  "compareDataType": "ALLOW_SAME_PARENTS",
  "compareSetSize": "ALLOW_SUPERSET",
  "name": "Custom Python Learner",
  "description": "...",
  "script": "...",
  "payload": "<Base64 인코딩된 pickle 데이터>",
  "defaultPython": true,
  "packageManager": "conda (anaconda)",
  "environment": null,
  "rm_object_annotations": { ... }
}
```

### 주요 필드 설명

| 필드 | 타입 | 내용 |
|---|---|---|
| `rm_object_type` | String | Java 클래스명 (`PythonModel`) |
| `rm_object_version` | String | AI Studio 버전 (`12.1.1`) |
| `headerExampleSet` | Object | 입력 피처 스키마 (컬럼명, 타입, 역할) |
| `compareDataType` | String | 스코어링 시 타입 호환성 정책 |
| `compareSetSize` | String | 스코어링 시 컬럼 수 호환성 정책 |
| `name` | String | 오퍼레이터 표시명 |
| `description` | String | 모델 객체의 `repr()` 문자열 |
| `script` | String | 학습에 사용된 Python 소스코드 원문 |
| **`payload`** | **String** | **Base64(Python pickle) — 실제 모델 객체** |

### `headerExampleSet` 구조

```json
{
  "@id": 1,
  "width": 49,
  "columns": [
    {"name": "KEY", "type": "Integer"},
    {"name": "R1_CBINQ_CNT05", "type": "Real"},
    ...
    {"name": "TARGET", "type": "Nominal", "role": "label", "dictionary": [null, "0", "1"]}
  ]
}
```

### `payload` 인코딩 방식

```
Base64 디코딩 → Python pickle (protocol 4)
첫 바이트: 80 04 (pickle magic bytes)
```

Python에서 복원 방법:

```python
import base64, pickle

payload_b64 = "..."  # JSON의 payload 값
model_dict = pickle.loads(base64.b64decode(payload_b64))
lgbm_model = model_dict["my_model"]  # LGBMClassifier 객체
```

> **주의**: pickle 파일은 신뢰할 수 없는 출처에서 로드 시 보안 위험이 있습니다.

---

## 3. `.rmtabmod` — LightGBM Extension 산출 모델

### 개요

**포맷: JSON**

`lightgbm:lightgbm` Extension 오퍼레이터로 학습한 모델의 저장 파일입니다. LightGBM 네이티브 모델 바이너리를 자체 인코딩 방식으로 직렬화합니다.

### JSON 구조

```json
{
  "rm_object_type": "com.rapidminer.extension.lightgbm.model.LightGBMModel",
  "rm_object_version": "12.1.1",
  "headerTable": { ... },
  "typeRequirements": ["REQUIRE_MATCHING_TYPES"],
  "columnSetRequirement": "EQUAL",
  "parameters": { ... },
  "iterations": 3000,
  "model": "z:<Base64 인코딩된 바이너리>",
  "rm_object_annotations": { ... }
}
```

### 주요 필드 설명

| 필드 | 타입 | 내용 |
|---|---|---|
| `rm_object_type` | String | Java 클래스명 (`LightGBMModel`) |
| `rm_object_version` | String | AI Studio 버전 (`12.1.1`) |
| `headerTable` | Object | 입력 피처 스키마 (컬럼명, 타입, 역할) |
| `typeRequirements` | Array | 스코어링 시 타입 호환성 정책 |
| `columnSetRequirement` | String | 스코어링 시 컬럼 수 호환성 정책 (`EQUAL`) |
| `parameters` | Object | LightGBM 하이퍼파라미터 원문 |
| `iterations` | Integer | 최종 트리 개수 |
| **`model`** | **String** | **`z:` 접두사 + Base64(LightGBM 네이티브 바이너리)** |

### `parameters` 필드 내용 (본 모델 기준)

```json
{
  "scale_pos_weight": 240,
  "boosting": "gbdt",
  "seed": 317,
  "max_depth": 3,
  "feature_fraction": 0.3,
  "verbose": -1,
  "min_gain_to_split": 0.5,
  "objective": "binary",
  "bagging_fraction": 1.0,
  "num_leaves": 8,
  "min_data_in_leaf": 800,
  "num_threads": 7,
  "lambda_l1": 15,
  "learning_rate": 0.005,
  "lambda_l2": 200
}
```

### `model` 인코딩 방식

```
"z:" 접두사 제거 → Base64 디코딩 → LightGBM 네이티브 바이너리
디코딩 크기: ~926KB
첫 바이트: D4 BD (표준 zlib 헤더 아님 → Extension 자체 직렬화 방식)
```

`z:` 접두사는 "compressed" 형식임을 나타내는 것으로 추정되나, RapidMiner LightGBM Extension 고유의 직렬화 포맷으로 외부 도구로 직접 복원하기 어렵습니다.

### `headerTable` 구조 (`.rmtabmod`)

`.rmmodel`의 `headerExampleSet`과 동일한 역할이지만 필드명이 다릅니다.

```json
{
  "columns": [
    {"name": "TARGET", "type": "Nominal", "role": "label"},
    {"name": "KEY", "type": "Integer", "role": "id"},
    {"name": "R1_CBINQ_CNT05", "type": "Real"},
    ...
  ]
}
```

---

## 파일 타입 비교 요약

| 항목 | `.rmp` | `.rmmodel` | `.rmtabmod` |
|---|---|---|---|
| **역할** | 프로세스(워크플로우) 정의 | Python Learner 모델 저장 | LightGBM Extension 모델 저장 |
| **포맷** | XML | JSON | JSON |
| **모델 본체** | 없음 | `payload`: Base64(pickle) | `model`: `z:` + Base64(바이너리) |
| **피처 스키마 필드** | — | `headerExampleSet` | `headerTable` |
| **하이퍼파라미터** | `<parameter>` 태그 | `script` 내 코드에 하드코딩 | `parameters` JSON 객체 |
| **생성 오퍼레이터** | — | `python_scripting:python_learner` | `lightgbm:lightgbm` |
| **파일 크기 (본 예시)** | ~10KB | ~3.8MB | ~1.2MB |
| **직렬화 방식** | — | Python pickle protocol 4 | LightGBM Extension 자체 포맷 |

---

## 참고: 스코어링 프로세스 흐름 (`test_scoring_process.rmp`)

```
Open File (test_data.csv)
  └→ Read CSV
       └→ Set Role (KEY → id)
            └→ Apply Model ←── Retrieve Model (261109_ext_lightgbm)
                 └→ Generate Attributes
                      └→ 신용점수 계산: max(0, min(1000, round(640 + 115.44 × log(conf(0)/conf(1)), 0)))
                           └→ Result
```

신용점수 변환 공식:

$$\text{Score} = \max\!\left(0,\ \min\!\left(1000,\ \text{round}\!\left(640 + 115.44 \times \log\!\frac{\text{conf}(0) + \epsilon}{\text{conf}(1) + \epsilon},\ 0\right)\right)\right)$$

여기서 $\epsilon = 10^{-10}$ (로그 0 방지용)
