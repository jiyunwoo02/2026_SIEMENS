# 트러블슈팅 기록 — create_lightgbm_process

**프로세스**: `기본 Python Extension 프로세스/create_lightgbm_process.rmp`  
**알고리즘**: LightGBM 이진 분류 (TARGET: 0/1)

---

## 이슈 1: Python Learner — missing label

### 증상
Python Learner 오퍼레이터 실행 시 `missing label` 에러 발생.

### 원인 분석

#### 1차 시도 (실패): `trim_lines = true`
- 헤더 첫 컬럼 구분자에 공백이 존재함: `TARGET, KEY,...` (`, KEY` — 쉼표 뒤 공백)
- Read CSV의 `trim_lines`는 **행 전체의 앞뒤 공백**만 제거하며, 필드 내부 공백은 제거하지 않음
- 결과: ` KEY` (공백+KEY) 가 여전히 파싱되어 근본 원인 미해결

#### 2차 원인 확정
- `blending:set_role` 오퍼레이터가 `KEY` 컬럼을 찾지 못함 (실제 컬럼명은 ` KEY`)
- Set Role 오퍼레이터가 실패하면서 `TARGET`의 label 역할도 설정되지 않음
- label 역할 없는 ExampleSet이 Python Learner로 전달 → `missing label` 에러

> **참고**: train_data.txt 전체 875,624행 중 TARGET 결측행 = 0건 (결측값 문제 아님)

### 해결
`create_lightgbm_process.rmp`의 Set Role 오퍼레이터에서 `KEY → id` 항목 제거.  
모델 학습에 id 역할은 불필요하며, `dropSpecial: true` 설정으로 Python Learner가 특수 컬럼을 자동 제외함.

```xml
<!-- 수정 전 -->
<list key="set_roles">
  <parameter key="TARGET" value="label"/>
  <parameter key="KEY" value="id"/>
</list>

<!-- 수정 후 -->
<list key="set_roles">
  <parameter key="TARGET" value="label"/>
</list>
```

**상태**: ✅ 해결

---

## 이슈 2: Python Learner — failed to run python code

### 증상
이슈 1 해결 후 Python Learner 오퍼레이터에서 `failed to run python code` 에러 발생.

### 원인 분석 (추정)

Python 코드 실행 자체가 실패하는 경우로, 가능한 원인은 아래 순서로 확인 필요:

| 우선순위 | 원인 | 확인 방법 |
|---|---|---|
| 1 | `lightgbm` 패키지 미설치 | conda 환경에서 `pip list \| grep lightgbm` |
| 2 | `import lightgbm` 버전 불일치 | AI Studio 로그의 Python traceback 확인 |
| 3 | TARGET 타입 문제 (Polynominal → LightGBM 처리) | 에러 메시지 상세 확인 |
| 4 | 메모리 부족 (875,624행 × 48 피처) | 시스템 리소스 확인 |

### 원인 확정

Altair AI Studio의 Python 실행 환경(`C:\Users\z005cm2w\AppData\Local\Altair\MF`, base conda)에 **lightgbm 패키지가 미설치** 상태였음.

> `신규 Python SDK 프로세스/SDK 파일/lgbm-2.9.0.zip`은 LightGBM 패키지가 아닌 **AI Studio Python SDK 익스텐션** 파일임 (Siemens_process의 `py_gbm` 오퍼레이터용). 기본 Python Extension 프로세스에는 직접 설치 필요.

### 해결

AI Studio의 Python binary path 설정이 Altair MF conda가 아닌 별도 Python312 환경을 가리키고 있었음.

| 항목 | 경로 |
|---|---|
| 최초 설치 (잘못된 환경) | `C:\Users\z005cm2w\AppData\Local\Altair\MF\Scripts\pip.exe` |
| 실제 AI Studio 사용 환경 | `C:\Users\z005cm2w\AppData\Local\Programs\Python\Python312` |

올바른 환경에 lightgbm 4.6.0 설치:

```powershell
C:\Users\z005cm2w\AppData\Local\Programs\Python\Python312\Scripts\pip.exe install "lightgbm==4.6.0"
# → lightgbm-4.6.0 설치 완료 (numpy, scipy는 이미 설치되어 있었음)
```

> AI Studio Settings > Python > Python binary path 확인 후 해당 환경의 pip으로 패키지를 설치해야 함.

**상태**: ✅ 해결

---

---

## 이슈 3: AI Hub 배포 후 — ExecutionError: The script could not be parsed

### 증상
AI Hub 엔드포인트로 POST 요청 시 아래 에러 반환:
```json
{"code":"ExecutionError","message":"The process execution has failed: 'The script could not be parsed.'. Detailed error message: 'Please check your Python script: '"}
```

### 원인
`ckj_scoring_process.rmp`의 Execute Python 오퍼레이터(`스코어산출_train`) 스크립트에  
**한글 주석** `# 2. 상수 계산` 이 포함되어 있었음.  
AI Hub 서버 Python 파서가 UTF-8 한글 문자를 처리하지 못해 parse error 발생.

### 추가 원인 (에러 지속)
- 실제 배포 파일이 Test 폴더가 아닌 `Projects/jiyoon-nice/deploy/deploy_scoring_process.rmp` 였음 → 이전 수정이 반영되지 않았음
- 한글 주석 제거 후에도 에러 지속 → 추가 원인 확인
  1. **불필요한 공백 라인** (`&#10; &#10;`) 이 함수 내부에 존재
  2. **numpy 의존성** — AI Hub 서버 환경에 numpy 없을 경우 import 실패가 "parse error"로 보고됨

### 해결
`numpy` 제거, `math` 모듈로 대체 + 불필요한 공백/빈 줄 전면 정리:

```python
# 수정 전
import pandas as pd
import numpy as np

def rm_main(data):

    anchor = 640
    pdo = 80
    
    factor = pdo / np.log(2)
    offset = anchor 

    p_pos = data['confidence(conf(1))'].values + 1e-10
    ...

# 수정 후
import math

def rm_main(data):
    anchor = 640
    factor = 80 / math.log(2)
    p_pos = data['confidence(conf(1))'] + 1e-10
    p_neg = data['confidence(conf(0))'] + 1e-10
    odds = p_neg / p_pos
    data['Score'] = anchor + factor * odds.apply(math.log)
    data['Score'] = data['Score'].clip(lower=0, upper=1000).round(0).astype(int)
    return data
```

**상태**: ✅ 해결 (재배포 후 확인 필요)

---

## 이슈 4: AI Hub 배포 후 — ExecutionError 지속 (근본 원인 확정)

### 증상
Execute Python 제거, Generate Attributes 대체, 재배포 후에도 동일한 에러 지속:
```json
{"code":"ExecutionError","message":"The process execution has failed: 'The script could not be parsed.'"}
```

### 근본 원인

**AI Hub 서버에 Python Extension이 미구성.**

에러가 Execute Python 오퍼레이터가 아닌 **Apply Model 단계**에서 발생.

```
[AI Hub 실행 흐름]
input → Apply Model ← (Retrieve) 261106_pyl_lightgbm.rmmodel
            ↓
     rm_apply() 호출  ← .rmmodel 내부에 Python 코드 내장
            ↓
  Python Extension 필요 → 미구성 → "script could not be parsed"
```

모델 파일(`.rmmodel`)은 `python_scripting:python_learner`로 학습된 모델로,  
Apply Model 실행 시 모델 내부의 `rm_apply()` Python 함수를 호출한다.  
AI Hub 서버에 Python Extension이 구성되어 있지 않아 이 단계에서 파싱 에러 발생.

Execute Python 오퍼레이터를 제거해도 에러가 지속된 이유가 이 때문이다.

### 해결을 위한 조건

| 방법 | 조건 |
|---|---|
| **A. Python Extension 구성** | AI Hub 서버에 Python 환경 경로 설정 (관리자 권한 필요) |
| **B. LightGBM Extension 전환** | JAR 익스텐션(`lightgbm_extension-1.0.4-all 1.jar`) 사용으로 Python 의존성 제거 → **v2에서 채택** |

### 상태: ✅ 해결 — LightGBM Extension(v2)으로 전환 완료, 엔드포인트 정상 운영 중

> v2 상세: [lightgbm.md](../lightgbm.md)

---

## 이슈 5: AI Hub — LightGBM Extension 미설치

### 증상
v2 엔드포인트 호출 시:
```json
{"code":"ExecutionError","message":"com.rapidminer.extension.lightgbm.model.LightGBMModel not registered for deserialization. Missing extension?."}
```

### 원인
AI Hub 서버에 LightGBM Extension JAR가 설치되어 있지 않아 `.rmtabmod` 모델 역직렬화 불가.

### 해결
AI Hub 서버에 `lightgbm_extension-1.0.4-all.jar` 설치 후 서버 재시작.

**상태**: ✅ 해결

---

## 이슈 6: AI Hub — KEY 속성 타입 불일치 (Real vs Integer)

### 증상
```json
{"code":"ExecutionError","message":"Attribute 'KEY' is of value type 'Real' but should be 'Integer'."}
```

### 원인
모델은 KEY를 Integer 피처로 학습했으나 API JSON 입력에서 숫자는 항상 Real(1 → 1.0)로 파싱됨.

### 해결
두 단계 적용:
1. `create_lightgbm_process_v0.2.rmp` Set Role에 `KEY → id` 추가 후 **재학습** → 모델이 KEY를 피처로 사용하지 않음
2. `deploy_scoring_process_v0.2.rmp`에 `Set Role (KEY → id)` 오퍼레이터를 Apply Model 앞에 추가 → 입력 데이터의 KEY 역할을 모델 학습 환경과 일치시킴

**상태**: ✅ 해결

---

## 이슈 7: AI Hub — confidence 컬럼명 불일치

### 증상
```json
{"code":"ExecutionError","message":"Error evaluating expression: The attribute 'confidence(conf(0))' is unknown."}
```

### 원인
Python Learner와 LightGBM Extension의 confidence 컬럼 명명 방식이 다름:

| Operator | confidence 컬럼명 |
|---|---|
| Python Learner | `confidence(conf(0))`, `confidence(conf(1))` |
| LightGBM Extension | `confidence(0)`, `confidence(1)` |

Python Learner는 `rm_apply()`에서 `f"conf({c})"` 로 직접 naming하고, LightGBM Extension은 TARGET 클래스명(`0`, `1`)을 그대로 사용.

### 해결
`deploy_scoring_process_v0.2.rmp`의 Generate Attributes Score 수식 수정:
```
# 수정 전
max(0, min(1000, round(640 + (115.44 * log(([confidence(conf(0))] + 0.0000000001) / ([confidence(conf(1))] + 0.0000000001))), 0)))

# 수정 후
max(0, min(1000, round(640 + (115.44 * log(([confidence(0)] + 1e-10) / ([confidence(1)] + 1e-10))), 0)))
```

**상태**: ✅ 해결

---

## 이슈 8: AI Studio — Score 수식 줄바꿈 삽입

### 증상
API 응답에서 Score가 숫자가 아닌 수식 문자열 그대로 반환됨:
```json
{"Score": "max(0, min(1000, round(640 + (115.44 * log(([confidence(0)] + 0.0000000001) / ([confidence(1)] + 0.\n0000000001))), 0)))"}
```

### 원인
AI Studio가 XML 파일 저장 시 긴 `value` 속성을 자동으로 줄바꿈 처리 → `0.0000000001`이 `0.&#10;0000000001`로 분리되어 수식 파싱 실패.

### 해결
`0.0000000001` → `1e-10` 으로 단축 (동일한 값, AI Studio가 줄바꿈하지 않는 길이):
```
max(0, min(1000, round(640 + (115.44 * log(([confidence(0)] + 1e-10) / ([confidence(1)] + 1e-10))), 0)))
```

> **주의**: AI Studio에서 이 파일을 열고 저장하면 재발할 수 있음. 배포 시 AI Studio에서 열지 않고 직접 파일 업로드 권장.

**상태**: ✅ 해결

---

## 체크리스트

- [x] missing label 에러 해결 (Set Role KEY 항목 제거)
- [x] failed to run python code 에러 해결 (lightgbm 4.6.0 설치)
- [x] 모델 학습 정상 완료 확인 (Python Learner, 3,000 trees)
- [x] 모델 저장 (`261106_pyl_lightgbm`) 확인
- [x] LightGBM Extension으로 전환 (v2, `261109_ext_lightgbm.rmtabmod`)
- [x] v2 엔드포인트 배포 (`mlops.nice.plda-cloud.com`)
- [x] AI Hub LightGBM Extension JAR 설치 (이슈 5)
- [x] LightGBM num_iterations=3000 정상 학습 확인
- [x] KEY 속성 타입 이슈 해결 (재학습 + Set Role 추가)
- [x] confidence 컬럼명 수식 수정
- [x] Score 수식 줄바꿈 이슈 해결 (1e-10)
- [x] v2 엔드포인트 Score 정상 응답 확인 ✅
