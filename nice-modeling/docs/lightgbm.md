# LightGBM 모델 상세 문서

NICE평가정보 신용평가 데이터 기반 LightGBM 이진 분류 모델의 구현 이력, 파라미터, 마이그레이션 가이드.

---

## 목차

1. [모델 개요](#1-모델-개요)
2. [하이퍼파라미터](#2-하이퍼파라미터)
3. [구현 방식 비교: Python Learner vs LightGBM Extension](#3-구현-방식-비교-python-learner-vs-lightgbm-extension)
4. [LightGBM Extension 마이그레이션 가이드](#4-lightgbm-extension-마이그레이션-가이드)
5. [신용점수 산출 공식](#5-신용점수-산출-공식)
6. [트러블슈팅](#6-트러블슈팅)

---

## 1. 모델 개요

| 항목 | 내용 |
|------|------|
| 알고리즘 | LightGBM Gradient Boosting (이진 분류) |
| 학습 데이터 | `train_data.txt` — 875,624행, 피처 47개 |
| 레이블 | `TARGET`: 0 (정상), 1 (불량) |
| 클래스 불균형 | 불량률 약 0.4% → `scale_pos_weight=240`으로 보정 |
| 출력 | P(정상), P(불량) → 오즈 로그 스케일링으로 0–1000점 변환 |

---

## 2. 하이퍼파라미터

### 현행 파라미터 (Python Learner 기준)

| 파라미터 | 값 | 역할 |
|----------|-----|------|
| `n_estimators` | 3,000 | 트리 수 (반복 횟수) |
| `learning_rate` | 0.005 | 학습률 — 낮게 설정, 트리 수로 보완 |
| `num_leaves` | 8 | 리프 노드 수 — `max_depth=3`보다 엄격하게 제한 |
| `max_depth` | 3 | 트리 최대 깊이 — 과적합 방지 |
| `min_child_samples` | 800 | 리프 최소 샘플 수 — 고불균형 데이터 안정성 확보 |
| `colsample_bytree` | 0.3 | 피처 샘플링 비율 (트리별) |
| `subsample` | 0.8 | 행 샘플링 비율 (**주의**: 실제 미적용, 아래 참고) |
| `reg_alpha` | 15 | L1 정규화 |
| `reg_lambda` | 200 | L2 정규화 — 강한 규제로 과적합 억제 |
| `min_split_gain` | 0.5 | 분할 최소 이득 |
| `scale_pos_weight` | 240 | 불량(1) 클래스 가중치 — 불균형 보정 |
| `random_state` | 317 | 재현성 고정 시드 |

> **subsample 주의**: sklearn `LGBMClassifier`에서 `subsample`(= LightGBM core `bagging_fraction`)은 `subsample_freq`(= `bagging_freq`)가 0(기본값)이면 **실제로 적용되지 않는다.** 원본 코드에 `subsample_freq` 미지정 → bagging 사실상 비활성화 상태였음.

---

## 3. 구현 방식 비교: Python Learner vs LightGBM Extension

| 항목 | Python Learner (기존) | LightGBM Extension (신규) |
|------|----------------------|--------------------------|
| 오퍼레이터 | `python_scripting:python_learner` | `lightgbm:lightgbm` (JAR 익스텐션) |
| Python 의존성 | AI Hub 서버에 Python Extension 필요 | **불필요** — 순수 Java 구현 |
| 모델 파일 | `.rmmodel` (Python 코드 내장) | `.rmtabmod` (Tabular Model, Java 직렬화) |
| AI Hub 호환성 | ⚠️ 서버 Python Extension 미구성 시 실행 오류 | ✅ 별도 환경 구성 없이 동작 |
| 파라미터 설정 | Python 코드 직접 수정 | UI 파라미터 패널 |

---

## 4. LightGBM Extension 마이그레이션 가이드

### 4-1. 익스텐션 정보

```
파일: lightgbm_extension-1.0.4-all 1.jar
위치: MXRM_Docs/03_PoC_BMT/나이스평가정보_20260402/20261106_process_전달/03.Extension/
```

### 4-2. 프로세스 구성 변경 사항

**기존 (Python Learner)**
```
Read CSV → Numerical to Polynominal → Set Role → Python Learner → Store
```

**신규 (LightGBM Extension)**
```
Read CSV → Numerical to Polynominal → Set Role → LightGBM → Store
```

> `Python Learner` 오퍼레이터를 `LightGBM` 오퍼레이터로 교체. 나머지 흐름은 동일.

### 4-3. 파라미터 매핑 — UI 직접 설정

| Python Learner (sklearn API) | LightGBM Extension UI 파라미터 | 설정값 |
|------------------------------|-------------------------------|--------|
| `n_estimators=3000` | **num iterations** | `3000` |
| `learning_rate=0.005` | **learning rate** | `0.005` |
| `num_leaves=8` | **num leaves** | `8` |
| `max_depth=3` | **max depth** | `3` |
| `min_child_samples=800` | **min data in leaf** | `800` |
| `colsample_bytree=0.3` | **feature fraction** | `0.3` |
| — | **boosting** | `gbdt` (기본값 유지) |
| — | **objective** | `auto` (기본값 유지, 이진 분류 자동 감지) |
| — | **early stopping** | `none` (기본값 유지) |

### 4-4. 파라미터 매핑 — Expert Parameters

`expert parameters` → `Edit Enumeration`에서 key-value 형식으로 추가:

| Python Learner | LightGBM Core 파라미터명 | 값 |
|----------------|-------------------------|----|
| `reg_alpha=15` | `lambda_l1` | `15` |
| `reg_lambda=200` | `lambda_l2` | `200` |
| `min_split_gain=0.5` | `min_gain_to_split` | `0.5` |
| `scale_pos_weight=240` | `scale_pos_weight` | `240` |
| `random_state=317` | `seed` | `317` |

### 4-5. bagging (subsample) 처리 — 선택 사항

원본 Python Learner에서 `subsample=0.8`은 `subsample_freq` 미지정으로 **실제 미적용** 상태였다.
Extension 전환 시 아래 중 하나를 선택:

| 옵션 | bagging fraction | Expert Params 추가 | 권장 상황 |
|------|-----------------|-------------------|---------|
| **A — 원본 동작 재현** | `1.0` (기본값 유지) | 없음 | 모델 결과 재현이 목적 |
| **B — bagging 활성화** | `0.8` | `bagging_freq=1` 추가 | 성능 개선도 함께 시도 |

> **권장**: 우선 옵션 A로 재현성 확인 후, 필요 시 옵션 B로 튜닝.

### 4-6. 최종 파라미터 요약표

```
[UI 파라미터]
boosting          : gbdt
num iterations    : 3000
objective         : auto
learning rate     : 0.005
num leaves        : 8
max depth         : 3
min data in leaf  : 800
feature fraction  : 0.3
bagging fraction  : 1.0  (옵션 A) 또는 0.8 (옵션 B)
early stopping    : none

[Expert Parameters]
lambda_l1         : 15
lambda_l2         : 200
min_gain_to_split : 0.5
scale_pos_weight  : 240
seed              : 317
(bagging_freq     : 1)   ← 옵션 B 선택 시에만 추가
```

---

## 5. 신용점수 산출 공식

모델 출력 `P(0)` (정상 확률), `P(1)` (불량 확률)로부터 신용점수 산출.

```
anchor = 640
pdo    = 80
factor = pdo / ln(2) ≈ 115.44

odds  = P(0) / P(1)
Score = anchor + factor × ln(odds)
Score = clip(0, 1000).round(0)
```

**AI Studio `Generate Attributes` 수식 (v2 기준):**
```
Score = max(0, min(1000, round(640 + (115.44 * log(([confidence(0)] + 1e-10) / ([confidence(1)] + 1e-10))), 0)))
```

> `1e-10`은 log(0) 방지용 epsilon. LightGBM Extension의 confidence 컬럼명은 `confidence(0)`, `confidence(1)` (Python Learner의 `confidence(conf(0))`와 다름).  
> `0.0000000001` 대신 `1e-10` 표기를 사용하는 이유: AI Studio XML 저장 시 긴 소수를 자동 줄바꿈하여 수식이 깨지는 현상 방지.

> 점수가 높을수록 우량. 640점 = odds 1:1 기준점 (불량/정상 확률 동일).

---

## 6. 트러블슈팅

| # | 증상 | 원인 | 해결 |
|---|------|------|------|
| 1 | Python Learner — missing label 오류 | 헤더 ` KEY` 앞 공백 → Set Role 충돌 | Set Role에서 `KEY → id` 항목 제거, `TARGET → label`만 유지 |
| 2 | Python Learner — `lightgbm` 패키지 미설치 | base conda 환경에 lightgbm 없음 | `pip install lightgbm==4.6.0` (Python312 환경) |
| 3 | AI Hub 배포 후 한글 주석·numpy 인코딩 에러 | 서버 Python Extension 환경 차이 | 한글 주석 제거, numpy 의존 코드 정리 |
| 4 | AI Hub 배포 후 `ExecutionError` | 서버 Python Extension 미구성 | LightGBM Extension으로 전환 ✅ |
| 5 | AI Hub — `LightGBMModel not registered for deserialization` | AI Hub 서버에 LightGBM Extension JAR 미설치 | 서버에 `lightgbm_extension-1.0.4-all.jar` 설치 ✅ |
| 6 | AI Hub — `KEY is of value type 'Real' but should be 'Integer'` | API JSON 입력의 숫자는 항상 Real로 파싱 | 학습 시 KEY를 id role로 설정 후 재학습 + 배포 프로세스에 Set Role 추가 ✅ |
| 7 | AI Hub — `attribute 'confidence(conf(0))' is unknown` | Python Learner와 LightGBM Extension의 confidence 컬럼명 상이 | Score 수식을 `confidence(0)`, `confidence(1)` 로 수정 ✅ |
| 8 | Score가 수식 문자열 그대로 반환 | AI Studio XML 저장 시 긴 소수(`0.0000000001`)에 자동 줄바꿈 삽입 | `1e-10` 으로 단축 ✅ |