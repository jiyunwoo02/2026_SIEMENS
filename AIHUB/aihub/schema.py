from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

# 교대조는 주간과 야간만 허용한다.
ALLOWED_SHIFTS: list[str] = ["DAY", "NIGHT"]
# 빈 목록이면 코드 목록 검사를 생략한다. 값을 등록하면 해당 코드만 허용한다.
ALLOWED_PRODUCTION_LINES: list[str] = []
ALLOWED_SUPPLIER_CODES: list[str] = []

# 추출값 정규화와 입력 안내에 사용하는 문자열·수치 필드 분류.
TEXT_FIELDS = ["production_line", "shift", "supplier_code"]
NUMERIC_FIELDS = [
    "planned_quantity",
    "ambient_humidity_pct",
    "incoming_material_quality_score",
    "coating_target_thickness_um",
    "weld_energy_setting_pct",
    "fixture_alignment_offset_mm",
    "process_setting_deviation_pct",
    "tool_wear_pct",
    "days_since_maintenance",
]
# 슬롯 검사와 API 전송용 딕셔너리 생성에 사용하는 12개 필드의 공통 순서.
ALL_FIELDS = TEXT_FIELDS + NUMERIC_FIELDS

# LLM 추출 프롬프트, JSON Schema, 추가 질문에서 함께 사용하는 필드 명세.
# 설명에 적힌 수치 범위의 실제 검증은 아래 DefectRateInput에서 수행한다.
FIELD_SPEC: dict[str, dict[str, Any]] = {
    "production_line": {"type": "string", "desc": "생산 라인 코드 (예: LINE-BPR-01)"},
    "shift": {"type": "string", "desc": "근무 교대조. DAY 또는 NIGHT"},
    "supplier_code": {"type": "string", "desc": "공급업체 코드 (예: SIM-SUP-B)"},
    "planned_quantity": {"type": "integer", "desc": "계획 생산 수량 (개), 0 이상"},
    "ambient_humidity_pct": {"type": "number", "desc": "작업장 습도 (%), 0~100"},
    "incoming_material_quality_score": {"type": "number", "desc": "입고 자재 품질 점수, 0~100"},
    "coating_target_thickness_um": {"type": "number", "desc": "코팅 목표 두께 (um = 마이크로미터), 0 이상"},
    "weld_energy_setting_pct": {"type": "number", "desc": "용접 에너지 설정값 (%), 0~150"},
    "fixture_alignment_offset_mm": {"type": "number", "desc": "지그 정렬 오프셋 (mm). 음수 가능"},
    "process_setting_deviation_pct": {"type": "number", "desc": "공정 설정 편차 (%)"},
    "tool_wear_pct": {"type": "number", "desc": "공구 마모도 (%), 0~100"},
    "days_since_maintenance": {"type": "integer", "desc": "마지막 정비 이후 경과 일수, 0 이상"},
}


class DefectRateInput(BaseModel):
    """예측 API로 보낼 단일 레코드의 필수 필드와 허용 범위를 정의한다."""

    # 모든 필드는 필수이며, 문자열은 정규화 후에도 한 글자 이상이어야 한다.
    production_line: str = Field(min_length=1)
    shift: str = Field(min_length=1)
    supplier_code: str = Field(min_length=1)
    # ge는 최솟값 이상, le는 최댓값 이하를 뜻하며 경계값도 허용한다.
    planned_quantity: int = Field(ge=0)
    ambient_humidity_pct: float = Field(ge=0, le=100)
    incoming_material_quality_score: float = Field(ge=0, le=100)
    coating_target_thickness_um: float = Field(ge=0)
    weld_energy_setting_pct: float = Field(ge=0, le=150)
    # 오프셋과 공정 편차에는 별도의 상·하한을 두지 않아 음수도 허용한다.
    fixture_alignment_offset_mm: float
    process_setting_deviation_pct: float
    tool_wear_pct: float = Field(ge=0, le=100)
    days_since_maintenance: int = Field(ge=0)

    @field_validator(*TEXT_FIELDS, mode="before")
    @classmethod
    def _normalize_text(cls, v: Any) -> Any:
        """기본 필드 검증 전에 문자열의 양끝 공백을 제거하고 대문자로 통일한다."""
        # 문자열이 아닌 값은 그대로 넘겨 Pydantic의 타입 검증을 받게 한다.
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("shift")
    @classmethod
    def _check_shift(cls, v: str) -> str:
        """정규화된 교대조 코드가 허용 목록에 있는지 확인한다."""
        if v not in ALLOWED_SHIFTS:
            raise ValueError(f"{ALLOWED_SHIFTS} 중 하나여야 합니다 (입력: '{v}')")
        return v

    @field_validator("production_line")
    @classmethod
    def _check_line(cls, v: str) -> str:
        """생산 라인 허용 목록이 설정된 경우에만 코드 포함 여부를 검사한다."""
        if ALLOWED_PRODUCTION_LINES and v not in ALLOWED_PRODUCTION_LINES:
            raise ValueError(f"{ALLOWED_PRODUCTION_LINES} 중 하나여야 합니다 (입력: '{v}')")
        return v

    @field_validator("supplier_code")
    @classmethod
    def _check_supplier(cls, v: str) -> str:
        """공급업체 허용 목록이 설정된 경우에만 코드 포함 여부를 검사한다."""
        if ALLOWED_SUPPLIER_CODES and v not in ALLOWED_SUPPLIER_CODES:
            raise ValueError(f"{ALLOWED_SUPPLIER_CODES} 중 하나여야 합니다 (입력: '{v}')")
        return v

    def to_row(self) -> dict[str, Any]:
        """검증된 모델에서 공통 입력 필드만 뽑아 전송용 딕셔너리로 변환한다."""
        return {f: getattr(self, f) for f in ALL_FIELDS}


def build_payload(records: list[DefectRateInput]) -> dict[str, Any]:
    """입력 순서를 유지하여 예측 API의 data 배열 요청 본문을 구성한다."""
    return {"data": [r.to_row() for r in records]}


class DefectRatePrediction(BaseModel):
    """단일 레코드의 예측값과 API 응답에 포함된 입력 에코 정보를 보관한다."""

    # 값 자체가 퍼센트 단위이다. 예: 1.65는 1.65%를 의미한다.
    defect_rate_pct: float
    # 예측 컬럼을 제외한 응답 필드. default_factory로 인스턴스마다 새 컨테이너를 만든다.
    echoed_input: dict[str, Any] = Field(default_factory=dict)
    # 요청에는 있지만 응답 에코에는 없는 입력 컬럼 이름.
    dropped_columns: list[str] = Field(default_factory=list)

    def format(self, digits: int = 2) -> str:
        """배율 변환 없이 지정한 소수 자릿수의 퍼센트 문자열로 표시한다."""
        return f"{self.defect_rate_pct:.{digits}f}%"


def extraction_json_schema() -> dict[str, Any]:
    """LLM이 미확정 값을 null로 표현할 수 있는 추출용 JSON Schema를 생성한다."""
    # 최종 입력 모델과 달리 각 필드에 null을 허용해 추가 입력이 필요한 상태를 표현한다.
    # 수치 범위는 설명으로 제공하며 이 스키마에 minimum/maximum 제약을 넣지는 않는다.
    props = {
        name: {
            "type": [spec["type"], "null"],
            "description": f"{spec['desc']}. 질의에 명시되지 않았으면 null.",
        }
        for name, spec in FIELD_SPEC.items()
    }
    # 최상위에는 records와 notes를 모두 요구하고 정의하지 않은 속성은 금지한다.
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["records", "notes"],
        "properties": {
            # 비교 조건은 여러 레코드로 표현할 수 있고, 빈 배열도 허용한다.
            "records": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    # 값이 미확정이어도 필드 키는 생략하지 않고 null로 채워야 한다.
                    "required": list(props.keys()),
                    "properties": props,
                },
            },
            # 부가 설명이 없으면 키를 생략하는 대신 null을 사용한다.
            "notes": {"type": ["string", "null"]},
        },
    }
