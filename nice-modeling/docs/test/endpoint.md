# NICE 신용평가 스코어링 API 엔드포인트

## 기본 정보

| 항목 | 값 |
|---|---|
| AI Hub 프로젝트 | `jiyoon-nice` |
| 서비스명 | `nice_score` |
| 프로세스명 | `deploy_scoring_process` |
| Endpoint URL | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/nice_score/deploy_scoring_process` |
| Method | `POST` |
| Content-Type | `application/json` |

---

## 요청 형식 (Request)

### Body 구조

```json
{
  "data": [
    {
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
      "R1_CF0600224": 0.0,
      "R1_CF1200143": 0.0,
      "R1_CF1200223": 0.0,
      "R1_CL1200915": 2.0
    }
  ]
}
```

### 주요 규칙

| 항목 | 설명 |
|---|---|
| `TARGET` 컬럼 | **포함하지 않음** (예측 대상) |
| `data` 배열 | 복수 행 동시 요청 가능 (객체를 여러 개 넣으면 됨) |
| 결측값 | `null` 사용 |

---

## 요청 예시

### cURL

```bash
curl -X POST "https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/nice_score/deploy_scoring_process" \
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

### Python

```python
import requests

url = "https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/nice_score/deploy_scoring_process"
headers = {"Content-Type": "application/json"}

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

response = requests.post(url, headers=headers, json=payload)
result = response.json()

# 점수 추출
score = result["data"][0]["Score"]
print(f"신용점수: {score}")
```

---

## 응답 형식 (Response)

```json
{
  "data": [
    {
      "KEY": 1,
      "prediction(TARGET)": "0",
      "confidence(conf(0))": 0.9821,
      "confidence(conf(1))": 0.0179,
      "Score": 812
    }
  ]
}
```

### 응답 필드 설명

| 필드 | 설명 |
|---|---|
| `prediction(TARGET)` | 예측 클래스 (`"0"`: 정상, `"1"`: 불량) |
| `confidence(conf(0))` | 정상일 확률 P(0), 0~1 |
| `confidence(conf(1))` | 불량일 확률 P(1), 0~1 |
| `Score` | 신용점수 (0~1000, 높을수록 우량) |

---

## 입력 컬럼 전체 목록

총 **48개** 컬럼 (`TARGET` 제외)

| 순서 | 컬럼명 | 타입 |
|---|---|---|
| 1 | KEY | integer |
| 2 | R1_CBINQ_CNT05 | real |
| 3 | R1_CBINQ_CNT10_CD | real |
| 4 | R1_CBINQ__CNT07_TL | real |
| 5 | R1_CBINQ_CNT6M_TZ | real |
| 6 | R1_CBINQ_GGN1Y | real |
| 7 | R1_INQPTN_1Y_FN_03_FN | real |
| 8 | R1_INQPTN_1Y_FN_07_PF | real |
| 9 | R1_INQPTN_6M_FN_15_Z4 | real |
| 10 | R1_INQPTN_1Y_FN_15_Z4 | real |
| 11 | R1_INQPTN_1Y_FN_15_SP | real |
| 12 | R1_INQPTN_6M_Z4_30_Z4 | real |
| 13 | R1_INQPTN_1Y_Z4_05_Z4 | real |
| 14 | R1_CBINQ_CNT03_DIFF | real |
| 15 | R1_CBINQ_CNT03_PF_RTO | real |
| 16 | R1_CBINQ_CNT05_RTO | real |
| 17 | R1_CPCBLA_CNT05_CL | real |
| 18 | R1_CPCBLA_CNT05 | real |
| 19 | R1_L24003800 | real |
| 20 | R1_ZS0000187 | real |
| 21 | R1_PS0001190 | real |
| 22 | R1_PS0001728 | real |
| 23 | R1_LA0100016 | real |
| 24 | R1_LA0200013 | real |
| 25 | R1_LA0300016 | real |
| 26 | R1_LA0400005 | real |
| 27 | R1_C00000151 | real |
| 28 | R1_C11061100 | real |
| 29 | R1_SC0301005 | real |
| 30 | R1_SC0602003 | real |
| 31 | R1_SC1201003 | real |
| 32 | R1_SC1202006 | real |
| 33 | R1_LC0000001 | real |
| 34 | R1_LC0024602 | real |
| 35 | R1_LC0099025 | real |
| 36 | R1_LC0300011 | real |
| 37 | R1_LC0600202 | real |
| 38 | R1_LC0699001 | real |
| 39 | R1_LC0900202 | real |
| 40 | R1_LC2400001 | real |
| 41 | R1_LC2424801 | real |
| 42 | R1_LC3600001 | real |
| 43 | R1_CF0100122 | real |
| 44 | R1_CF0300939 | real |
| 45 | R1_CF0600224 | real |
| 46 | R1_CF1200143 | real |
| 47 | R1_CF1200223 | real |
| 48 | R1_CL1200915 | real |
