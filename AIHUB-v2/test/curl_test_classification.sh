# 최적화 API Curl
# 02 Optimization & Classification (GBT) 
# URL: https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization

# 1. 기본 호출 (curl)
curl -G -i --max-time 180 \
  "https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization" \
  --data-urlencode "target=1"

# 2. 매크로 반영 확인
URL="https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization"

curl -G -s --max-time 180 "$URL" --data-urlencode "target=1" | python -m json.tool > out_1.json
curl -G -s --max-time 180 "$URL" --data-urlencode "target=0" | python -m json.tool > out_0.json

diff out_1.json out_0.json && echo "동일: 매크로가 반영되지 않았을 수 있음"

# 3. 응답 시간 확인
curl -G -s -o /dev/null -w "상태: %{http_code}  소요: %{time_total}s\n" \
  --max-time 180 "$URL" --data-urlencode "target=1"