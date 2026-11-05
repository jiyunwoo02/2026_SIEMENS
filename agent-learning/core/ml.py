"""
core/ml.py
AI Hub GBT 결함률 예측 ML API의 HTTP 호출을 담당합니다.

함수 이름, 비즈니스 로직, 파라미터 처리 등은 tools/functions.py가 담당합니다.
여기서는 오직 "HTTP 요청 → 응답 파싱"만 처리합니다.
"""
from __future__ import annotations

import httpx

from core.config import ML_URL, MOCK_ML

# ML API 응답에서 예측값을 담은 컬럼명
_PRED_COLUMN = "prediction(defect_rate_pct)"


def call_ml_api(row: dict) -> float:
    """
    12개 피처 딕셔너리를 ML API에 전송하고 예측 결함률(%)을 반환합니다.

    Args:
        row: 12개 피처를 담은 딕셔너리
             {"production_line": ..., "shift": ..., ...}

    Returns:
        결함률 예측값 (퍼센트 단위. 예: 1.85 → 1.85%)

    Raises:
        RuntimeError: API 호출 실패 또는 응답 파싱 오류
    """
    if MOCK_ML or not ML_URL:
        return _mock_predict(row)

    payload = {"data": [row]}
    try:
        with httpx.Client(timeout=30.0, verify=False) as client:
            resp = client.post(
                ML_URL,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
        resp.raise_for_status()
        body = resp.json()

        # 응답 형식: {"data": [{...echo..., "prediction(defect_rate_pct)": float}]}
        rows = body.get("data", body) if isinstance(body, dict) else body
        return float(rows[0][_PRED_COLUMN])

    except (httpx.HTTPError, KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"ML API 호출 실패: {e}") from e


def _mock_predict(row: dict) -> float:
    """
    실제 API 없이 테스트할 때 사용하는 간단한 모의 예측.
    공구 마모·정비 경과일이 높을수록, 자재 품질이 낮을수록 결함률이 높아집니다.
    """
    base = 1.5
    return round(
        base
        + row.get("tool_wear_pct", 0)       * 0.015
        + row.get("days_since_maintenance", 0) * 0.02
        - row.get("incoming_material_quality_score", 80) * 0.01,
        2,
    )
