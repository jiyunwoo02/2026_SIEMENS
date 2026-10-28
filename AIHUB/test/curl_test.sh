# 우선 API 작동 여부 검증

# 01 Regression(GBT)
# 아래 명령어 복사하여 셸에 입력 -> 200 OK 반환되어야 함
curl -s -w '\n[HTTP %{http_code}] %{time_total}s\n' \
  https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_rate_pred/deploy \
  -X POST -H 'Content-type: application/json' \
  -d '{"data":[{"production_line":"LINE-BPR-01","shift":"DAY","supplier_code":"SIM-SUP-B","planned_quantity":533,"ambient_humidity_pct":54.49,"incoming_material_quality_score":83.95,"coating_target_thickness_um":79.22,"weld_energy_setting_pct":92.67,"fixture_alignment_offset_mm":0.112,"process_setting_deviation_pct":13.06,"tool_wear_pct":14.41,"days_since_maintenance":30}]}'


# 반환 결과 확인:
# - HTTP 200 코드
# - 실행 시간 (예: 0.001초)
# - JSON 응답 확인 (예: {"predictions": [0.0312, ...]})

# 실행 결과
# {"data":[{"production_line":"LINE-BPR-01","shift":"DAY","supplier_code":"SIM-SUP-B","planned_quantity":533.0,"ambient_humidity_pct":54.49,"incoming_material_quality_score":83.95,"coating_target_thickness_um":79.22,"weld_energy_setting_pct":92.67,"fixture_alignment_offset_mm":0.112,"process_setting_deviation_pct":13.06,"tool_wear_pct":14.41,"days_since_maintenance":30.0,"prediction(defect_rate_pct)":1.649867890802181}]}
# [HTTP 200] 0.547356s

# 최적화 API Curl
# 02 Optimization & Classification (GBT) 
# URL: https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization