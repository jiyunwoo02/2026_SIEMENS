from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

# 교대조는 주간과 야간만 허용한다.
ALLOWED_SHIFTS: list[str] = ["DAY", "NIGHT"]
# [수정] docs/input_schema.md 확정: 실제 운영 라인은 2종, 공급사는 3종뿐이라 화이트리스트를 등록한다.
# 빈 목록이면 코드 목록 검사를 생략한다. 값을 등록하면 해당 코드만 허용한다.
ALLOWED_PRODUCTION_LINES: list[str] = ["LINE-BPR-01", "LINE-BPR-02"]
ALLOWED_SUPPLIER_CODES: list[str] = ["SIM-SUP-A", "SIM-SUP-B", "SIM-SUP-C"]

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

# [추가] 2026-10-27: 최적화 기능 도입에 따른 챗봇 의도 분류.
# predict는 기존 결함률 예측(동작 유지), 나머지는 docs/agent-v2/bak/
# chatbot_optimization_feature_spec.md 5.3에서 정의한 신규 최적화 의도다.
# enum에 없는 값이나 누락된 값은 파이프라인에서 "clarify"로 처리한다(5.4 참고).
# [수정] 2026-10-29: predict_and_optimize는 "예측 + 불량 감소(개선) 조건"만 표현할 수 있어,
# "예측 + 불량 위험(악화) 조건"을 함께 요청하는 발화를 표현할 enum 값이 없었다. 그런 발화가
# predict_and_optimize로 분류되면 target이 "1"(불량 최소화)로 고정 호출돼 사용자가 원한 방향과
# 반대 결과가 나가는 문제가 있어 predict_and_find_risk를 추가했다(optimization.INTENT_TO_TARGET,
# pipeline._run_predict_and_optimize, llm.py [의도 분류] 절도 함께 수정).
INTENTS: list[str] = [
    "predict",
    "optimize_reduce_defect",
    "optimize_find_defect_risk",
    "predict_and_optimize",
    "predict_and_find_risk",
    "clarify",
]

# [추가] 2026-10-27: 최적화 API가 돌려주는 12개 조건 키 -> 한글 라벨.
# web/app.js의 welcomeMessage 문구와 표현을 맞춰 UI 전체에서 같은 용어를 쓴다.
# (현재는 두 곳에 같은 문자열이 중복돼 있다. 스키마가 바뀌면 두 곳 모두 수정해야 한다.)
FIELD_LABELS: dict[str, str] = {
    "production_line": "생산 라인",
    "shift": "교대조",
    "supplier_code": "공급사 코드",
    "planned_quantity": "계획 생산 수량(개)",
    "ambient_humidity_pct": "작업장 습도(%)",
    "incoming_material_quality_score": "입고 자재 품질점수",
    "coating_target_thickness_um": "코팅 목표 두께(um)",
    "weld_energy_setting_pct": "용접 에너지 설정(%)",
    "fixture_alignment_offset_mm": "지그 정렬 오프셋(mm)",
    "process_setting_deviation_pct": "공정 설정 편차(%)",
    "tool_wear_pct": "공구 마모도(%)",
    "days_since_maintenance": "마지막 정비 후 경과 일수",
}

# [추가] 2026-10-27: 현장에서 즉시 바꾸기 어려운 변수. 최적화 결과 표에서 "참고값"으로 표기해
# 사용자가 바꿀 수 없는 값을 조정 대상으로 오해하지 않게 한다.
# [수정] 2026-10-27: 비활성화 요청에 따라 기본 5개(shift, supplier_code, planned_quantity,
# ambient_humidity_pct, production_line)를 제거해 빈 집합으로 변경했다(로직 변경).
# 이 상수를 import하는 코드가 깨지지 않도록 이름은 유지한다. 빈 집합이면 모든 변수가 조정 대상으로 취급된다.
# 다시 활성화하려면 아래 집합에 필드명을 추가한다.
# [확인 필요] 명세(4.5/6.4)가 예시로 든 5개를 기본값으로 썼다. 실제 현장에서 바꿀 수 있는 변수
# 목록은 담당자 확인 후 조정해야 한다.
UNCONTROLLABLE_FIELDS: frozenset[str] = frozenset()

# LLM 추출 프롬프트, JSON Schema, 추가 질문에서 함께 사용하는 필드 명세.
# 설명에 적힌 수치 범위의 실제 검증은 아래 DefectRateInput에서 수행한다.
FIELD_SPEC: dict[str, dict[str, Any]] = {
    # [수정] 화이트리스트 확정에 맞춰 설명에 허용값을 명시해 추출 단계의 추측(환각)을 줄인다.
    # [수정] "~ 중 하나" 표현은 LLM이 허용값 밖 코드(LINE-BPR-03 등)를 null이나 비슷한 값으로 바꾸도록 유도할 수 있어
    # "허용값" 안내로 바꾼다. 허용값 밖 코드는 그대로 추출돼 DefectRateInput에서 invalid_input으로 차단돼야 한다(골든 I04, I05).
    "production_line": {"type": "string", "desc": "생산 라인 코드 (허용값: LINE-BPR-01, LINE-BPR-02)"},
    "shift": {"type": "string", "desc": "근무 교대조 (허용값: DAY, NIGHT)"},
    "supplier_code": {"type": "string", "desc": "공급업체 코드 (허용값: SIM-SUP-A, SIM-SUP-B, SIM-SUP-C)"},
    "planned_quantity": {"type": "integer", "desc": "계획 생산 수량 (개), 0 이상"},
    "ambient_humidity_pct": {"type": "number", "desc": "작업장 습도 (%), 0~100"},
    "incoming_material_quality_score": {"type": "number", "desc": "입고 자재 품질 점수, 0~100"},
    "coating_target_thickness_um": {"type": "number", "desc": "코팅 목표 두께 (um = 마이크로미터), 0 이상"},
    "weld_energy_setting_pct": {"type": "number", "desc": "용접 에너지 설정값 (%), 0~150"},
    # [수정] docs/input_schema.md 확정: 오프셋은 0 이상만 유효(음수 불가)하여 설명을 갱신한다.
    "fixture_alignment_offset_mm": {"type": "number", "desc": "지그 정렬 오프셋 (mm), 0 이상"},
    "process_setting_deviation_pct": {"type": "number", "desc": "공정 설정 편차 (%)"},
    "tool_wear_pct": {"type": "number", "desc": "공구 마모도 (%), 0~100"},
    "days_since_maintenance": {"type": "integer", "desc": "마지막 정비 이후 경과 일수, 0 이상"},
}


class DefectRateInput(BaseModel):
    """예측 API로 보낼 단일 레코드의 필수 필드와 허용 범위를 정의한다."""

    # 모든 필드는 필수이며, 문자열은 정규화 후에도 한 글자 이상이어야 한다.
    # [검토] docs/input_schema.md의 확정 하드 제약은 코드 3종 화이트리스트, 오프셋>=0, 마모율 0~100뿐이다.
    # 수량>=0, 습도·품질점수 0~100, 용접 0~150, 두께·경과일>=0은 사양에 없는 물리적 타당성 검사로 기존 코드에서 유지한다.
    # (골든 셋 v2 어느 케이스도 이 검사에 걸리지 않음. 유지 여부는 architecture.md 미결 사항에서 결정)
    production_line: str = Field(min_length=1)
    shift: str = Field(min_length=1)
    supplier_code: str = Field(min_length=1)
    # ge는 최솟값 이상, le는 최댓값 이하를 뜻하며 경계값도 허용한다.
    planned_quantity: int = Field(ge=0)
    ambient_humidity_pct: float = Field(ge=0, le=100) # ge: Greater than or equal
    incoming_material_quality_score: float = Field(ge=0, le=100)
    coating_target_thickness_um: float = Field(ge=0)
    weld_energy_setting_pct: float = Field(ge=0, le=150)
    # [수정] docs/input_schema.md 확정: 오프셋은 0 이상이어야 하므로 하한을 추가한다(이전: 하한 없음, 음수 허용).
    fixture_alignment_offset_mm: float = Field(ge=0)
    # 공정 편차는 별도의 상·하한을 두지 않아 음수도 허용한다.
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


# [추가] 2026-10-23: 필드 단위 검증용 기준 행. 모든 값이 유효하므로, 검사할 필드만 바꿔 넣으면
# 해당 필드의 위반만 결과에 나타난다. 검증 규칙은 DefectRateInput 한 곳에서만 관리한다(중복 정의 금지).
_VALID_REFERENCE_ROW: dict[str, Any] = {
    "production_line": ALLOWED_PRODUCTION_LINES[0] if ALLOWED_PRODUCTION_LINES else "LINE-REF",
    "shift": "DAY",
    "supplier_code": ALLOWED_SUPPLIER_CODES[0] if ALLOWED_SUPPLIER_CODES else "SUP-REF",
    "planned_quantity": 500,
    "ambient_humidity_pct": 50.0,
    "incoming_material_quality_score": 80.0,
    "coating_target_thickness_um": 80.0,
    "weld_energy_setting_pct": 100.0,
    "fixture_alignment_offset_mm": 0.1,
    "process_setting_deviation_pct": 0.0,
    "tool_wear_pct": 10.0,
    "days_since_maintenance": 10,
}


def validate_provided_fields(values: dict[str, Any]) -> dict[str, str]:
    """일부 필드만 채워진 상태에서도 값이 있는 필드를 개별 검증한다.

    [추가] 2026-10-23: 슬롯이 12개 모두 차기 전에는 DefectRateInput 검증이 실행되지 않아
    허용값 밖 코드(예: SIM-SUP-D)가 세션에 저장되던 문제를 막기 위해 추가했다.

    입력: 필드명 -> 값 딕셔너리. None인 값은 "미확정"이므로 검사하지 않는다.
    출력: 위반한 필드명 -> 오류 메시지. 위반이 없으면 빈 딕셔너리.
    예외: 발생시키지 않는다(위반은 반환값으로 알린다).
    """
    provided = {k: v for k, v in values.items() if k in ALL_FIELDS and v is not None}
    if not provided:
        return {}
    try:
        DefectRateInput(**{**_VALID_REFERENCE_ROW, **provided})
    except ValidationError as e:
        # 기준 행은 항상 유효하므로, 위반은 실제로 넘겨받은 필드에서만 발생한다.
        return {
            str(err["loc"][0]): err["msg"]
            for err in e.errors()
            if err["loc"] and str(err["loc"][0]) in provided
        }
    return {}


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
        # [수정] strict 모드는 모든 속성이 required여야 하므로 ambiguous_fields도 추가한다.
        # [수정] 2026-10-27: 의도 분류(intent)를 추가했다. strict 모드는 모든 속성이
        # required여야 하므로 required 목록에도 추가한다.
        "required": ["intent", "records", "ambiguous_fields", "notes"],
        "properties": {
            # [추가] 2026-10-27: 예측/최적화 의도 분류. llm.py의 [의도 분류] 지침과 함께 사용한다.
            "intent": {"type": "string", "enum": list(INTENTS)},
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
            # [추가] 모호한 표현 때문에 null로 둔 필드명. 대화 응답의 ambiguous_fields와
            # 되묻기 문구("값이 없습니다"가 아니라 "수치로 알려주세요")를 만드는 데 쓴다.
            "ambiguous_fields": {
                "type": "array",
                "items": {"type": "string", "enum": list(ALL_FIELDS)},
            },
            # 부가 설명이 없으면 키를 생략하는 대신 null을 사용한다.
            "notes": {"type": ["string", "null"]},
        },
    }
