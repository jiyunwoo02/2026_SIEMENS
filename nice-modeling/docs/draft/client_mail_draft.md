# 고객사 송부 메일 초안

**제목**: NICE 신용점수 모델 개발 및 대시보드 구축 결과 전달

---

안녕하세요, [발신자명]입니다.

이번에 진행한 NICE평가정보 신용점수 산출 모델 개발 및 시각화 대시보드 구축 결과를 아래와 같이 정리하여 전달드립니다.

---

## 1. 모델 개발

NICE평가정보 CB 데이터(학습 875,624건, 입력 피처 47개)를 기반으로 LightGBM 이진 분류 모델을 구축하였습니다. 모델은 각 고객의 정상(0) / 불량(1) 확률을 산출하며, 아래 공식에 따라 신용점수(0–1,000점)로 변환됩니다.

> Score = 640 + 115.44 × ln(정상확률 / 불량확률)

| 계수 | 의미 |
|------|------|
| **640** | 기준점(anchor) — 정상·불량 확률이 50:50일 때 산출되는 점수 |
| **115.44** | 배율(factor) — odds가 2배가 될 때 점수가 80점 상승하도록 설정한 값 (= 80 ÷ ln2) |

점수가 높을수록 신용 우량이며, 640점 미만은 불량 확률이 정상 확률보다 높은 구간입니다.

---

## 2. AI Hub API 명세 (v2, 운영 중)

### 엔드포인트

| 항목 | 내용 |
|------|------|
| URL | `https://mlops.nice.plda-cloud.com/webapi/DEFAULT/api/v1/services/nice-scoring/deploy_scoring_process_v02` |
| Method | `POST` |
| Content-Type | `application/json` |
| 인증 | 없음 |

### 요청 구조

```json
{
  "data": [
    {
      "KEY": 1,
      "R1_CBINQ_CNT05": 0.0,
      "...": "..."
    }
  ]
}
```

- `data` 배열에 복수 건 동시 요청 가능
- `TARGET` 컬럼은 **포함하지 않음** (예측 대상)
- 결측값은 `null` 사용

### 입력 컬럼 목록 (총 48개)

| 순서 | 컬럼명 | 타입 |
|------|--------|------|
| 1 | `KEY` | integer |
| 2 | `R1_CBINQ_CNT05` | real |
| 3 | `R1_CBINQ_CNT10_CD` | real |
| 4 | `R1_CBINQ__CNT07_TL` | real |
| 5 | `R1_CBINQ_CNT6M_TZ` | real |
| 6 | `R1_CBINQ_GGN1Y` | real |
| 7 | `R1_INQPTN_1Y_FN_03_FN` | real |
| 8 | `R1_INQPTN_1Y_FN_07_PF` | real |
| 9 | `R1_INQPTN_6M_FN_15_Z4` | real |
| 10 | `R1_INQPTN_1Y_FN_15_Z4` | real |
| 11 | `R1_INQPTN_1Y_FN_15_SP` | real |
| 12 | `R1_INQPTN_6M_Z4_30_Z4` | real |
| 13 | `R1_INQPTN_1Y_Z4_05_Z4` | real |
| 14 | `R1_CBINQ_CNT03_DIFF` | real |
| 15 | `R1_CBINQ_CNT03_PF_RTO` | real |
| 16 | `R1_CBINQ_CNT05_RTO` | real |
| 17 | `R1_CPCBLA_CNT05_CL` | real |
| 18 | `R1_CPCBLA_CNT05` | real |
| 19 | `R1_L24003800` | real |
| 20 | `R1_ZS0000187` | real |
| 21 | `R1_PS0001190` | real |
| 22 | `R1_PS0001728` | real |
| 23 | `R1_LA0100016` | real |
| 24 | `R1_LA0200013` | real |
| 25 | `R1_LA0300016` | real |
| 26 | `R1_LA0400005` | real |
| 27 | `R1_C00000151` | real |
| 28 | `R1_C11061100` | real |
| 29 | `R1_SC0301005` | real |
| 30 | `R1_SC0602003` | real |
| 31 | `R1_SC1201003` | real |
| 32 | `R1_SC1202006` | real |
| 33 | `R1_LC0000001` | real |
| 34 | `R1_LC0024602` | real |
| 35 | `R1_LC0099025` | real |
| 36 | `R1_LC0300011` | real |
| 37 | `R1_LC0600202` | real |
| 38 | `R1_LC0699001` | real |
| 39 | `R1_LC0900202` | real |
| 40 | `R1_LC2400001` | real |
| 41 | `R1_LC2424801` | real |
| 42 | `R1_LC3600001` | real |
| 43 | `R1_CF0100122` | real |
| 44 | `R1_CF0300939` | real |
| 45 | `R1_CF0600224` | real |
| 46 | `R1_CF1200143` | real |
| 47 | `R1_CF1200223` | real |
| 48 | `R1_CL1200915` | real |

### 응답 구조

응답은 요청 시 송신한 전체 컬럼(KEY + 피처 47개)을 그대로 포함하며, 아래 추론 결과 필드 4개가 추가됩니다.

| 필드 | 타입 | 설명 |
|------|------|------|
| `prediction(TARGET)` | string | 예측 클래스 (`"0"`: 정상, `"1"`: 불량) |
| `confidence(0)` | float | 정상일 확률 (0–1) |
| `confidence(1)` | float | 불량일 확률 (0–1) |
| `Score` | float | 신용점수 (0–1,000, 높을수록 우량) |

응답 예시:

```json
{
  "data": [
    {
      "KEY": 1,
      "R1_CBINQ_CNT05": 2.0,
      "...": "...",
      "prediction(TARGET)": "0",
      "confidence(0)": 0.9821,
      "confidence(1)": 0.0179,
      "Score": 928
    }
  ]
}
```

### 요청 예시

**cURL**

```bash
curl -X POST "https://mlops.nice.plda-cloud.com/webapi/DEFAULT/api/v1/services/nice-scoring/deploy_scoring_process_v02" \
  -H "Content-Type: application/json" \
  -d '{
    "data": [{
      "KEY": 1,
      "R1_CBINQ_CNT05": 2.0,
      "R1_CBINQ_CNT10_CD": 1.0,
      "R1_CBINQ__CNT07_TL": 1.0,
      "R1_CBINQ_CNT6M_TZ": 1.0,
      "R1_CBINQ_GGN1Y": 2.0,
      "R1_INQPTN_1Y_FN_03_FN": 3.0,
      "R1_INQPTN_1Y_FN_07_PF": 2.0,
      "R1_INQPTN_6M_FN_15_Z4": 4.0,
      "R1_INQPTN_1Y_FN_15_Z4": 2.0,
      "R1_INQPTN_1Y_FN_15_SP": 3.0,
      "R1_INQPTN_6M_Z4_30_Z4": 2.0,
      "R1_INQPTN_1Y_Z4_05_Z4": 2.0,
      "R1_CBINQ_CNT03_DIFF": 1.0,
      "R1_CBINQ_CNT03_PF_RTO": 2.0,
      "R1_CBINQ_CNT05_RTO": 2.0,
      "R1_CPCBLA_CNT05_CL": 0.0,
      "R1_CPCBLA_CNT05": 1.0,
      "R1_L24003800": 3.0,
      "R1_ZS0000187": 3.0,
      "R1_PS0001190": 0.0,
      "R1_PS0001728": 0.0,
      "R1_LA0100016": 4.0,
      "R1_LA0200013": 4.0,
      "R1_LA0300016": 4.0,
      "R1_LA0400005": 3.0,
      "R1_C00000151": 0.0,
      "R1_C11061100": 0.0,
      "R1_SC0301005": 2.0,
      "R1_SC0602003": 2.0,
      "R1_SC1201003": 1.0,
      "R1_SC1202006": 1.0,
      "R1_LC0000001": 1.0,
      "R1_LC0024602": 0.0,
      "R1_LC0099025": 0.0,
      "R1_LC0300011": 0.0,
      "R1_LC0600202": 0.0,
      "R1_LC0699001": 0.0,
      "R1_LC0900202": 0.0,
      "R1_LC2400001": 0.0,
      "R1_LC2424801": 0.0,
      "R1_LC3600001": 0.0,
      "R1_CF0100122": 0.0,
      "R1_CF0300939": 1.0,
      "R1_CF0600224": 0.0,
      "R1_CF1200143": 0.0,
      "R1_CF1200223": 0.0,
      "R1_CL1200915": 2.0
    }]
  }'
```

**Python**

```python
import requests

url = "https://mlops.nice.plda-cloud.com/webapi/DEFAULT/api/v1/services/nice-scoring/deploy_scoring_process_v02"

payload = {
    "data": [{
        "KEY": 1,
        "R1_CBINQ_CNT05": 2.0,
        "R1_CBINQ_CNT10_CD": 1.0,
        "R1_CBINQ__CNT07_TL": 1.0,
        "R1_CBINQ_CNT6M_TZ": 1.0,
        "R1_CBINQ_GGN1Y": 2.0,
        "R1_INQPTN_1Y_FN_03_FN": 3.0,
        "R1_INQPTN_1Y_FN_07_PF": 2.0,
        "R1_INQPTN_6M_FN_15_Z4": 4.0,
        "R1_INQPTN_1Y_FN_15_Z4": 2.0,
        "R1_INQPTN_1Y_FN_15_SP": 3.0,
        "R1_INQPTN_6M_Z4_30_Z4": 2.0,
        "R1_INQPTN_1Y_Z4_05_Z4": 2.0,
        "R1_CBINQ_CNT03_DIFF": 1.0,
        "R1_CBINQ_CNT03_PF_RTO": 2.0,
        "R1_CBINQ_CNT05_RTO": 2.0,
        "R1_CPCBLA_CNT05_CL": 0.0,
        "R1_CPCBLA_CNT05": 1.0,
        "R1_L24003800": 3.0,
        "R1_ZS0000187": 3.0,
        "R1_PS0001190": 0.0,
        "R1_PS0001728": 0.0,
        "R1_LA0100016": 4.0,
        "R1_LA0200013": 4.0,
        "R1_LA0300016": 4.0,
        "R1_LA0400005": 3.0,
        "R1_C00000151": 0.0,
        "R1_C11061100": 0.0,
        "R1_SC0301005": 2.0,
        "R1_SC0602003": 2.0,
        "R1_SC1201003": 1.0,
        "R1_SC1202006": 1.0,
        "R1_LC0000001": 1.0,
        "R1_LC0024602": 0.0,
        "R1_LC0099025": 0.0,
        "R1_LC0300011": 0.0,
        "R1_LC0600202": 0.0,
        "R1_LC0699001": 0.0,
        "R1_LC0900202": 0.0,
        "R1_LC2400001": 0.0,
        "R1_LC2424801": 0.0,
        "R1_LC3600001": 0.0,
        "R1_CF0100122": 0.0,
        "R1_CF0300939": 1.0,
        "R1_CF0600224": 0.0,
        "R1_CF1200143": 0.0,
        "R1_CF1200223": 0.0,
        "R1_CL1200915": 2.0
    }]
}

response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
result = response.json()

row = result["data"][0]
print(f"신용점수: {row['Score']}")
print(f"등급 판정: {row['prediction(TARGET)']}  (0=정상, 1=불량)")
print(f"정상 확률: {row['confidence(0)']:.4f}")
print(f"불량 확률: {row['confidence(1)']:.4f}")
```

---

## 3. 판옵티콘 대시보드 (`261112_검수.exz`)

47개 CB 변수 슬라이더를 조작하면 AI Hub 엔드포인트가 실시간 호출되어 신용점수·등급·확률이 즉시 갱신됩니다. 반원형 게이지로 점수 위치를 직관적으로 확인할 수 있으며, 점수 구간별 등급이 함께 표시됩니다.

| 점수 구간 | 등급 |
|-----------|------|
| 900 이상 | 최우수 |
| 800 – 899 | 우수 |
| 700 – 799 | 양호 |
| 600 – 699 | 보통 |
| 500 – 599 | 주의 |
| 500 미만 | 위험 |

> **사용 환경**: Panopticon Designer, Python 서버 기동 필요 (`pandas`, `requests`)

---

상세 내용은 첨부 문서를 참고 부탁드립니다.
추가 문의 사항이 있으시면 편하게 연락 주십시오.

감사합니다.
[발신자명] 드림

---

## 첨부 파일

- `NICE_ML_PROCESS_OVERVIEW.html` — 모델 개요
- `NICE_VISUALIZATION_PROCESS_OVERVIEW.html` — 대시보드 개요
- `261112_검수.exz` — 판옵티콘 대시보드 파일
