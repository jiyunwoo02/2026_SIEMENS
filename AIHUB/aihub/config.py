from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수와 .env 파일에서 애플리케이션 설정을 읽고 타입을 검증한다."""

    # 현재 작업 디렉터리의 .env를 UTF-8로 읽는다.
    # 환경 변수가 .env 값보다 우선하며, 정의하지 않은 설정 키는 무시한다.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # LLM 인증 키는 api_key와 llm_api_key 두 이름을 모두 허용한다.
    api_key: str = Field(default="", validation_alias=AliasChoices("api_key", "llm_api_key"))
    # LLM 게이트웨이 기본 주소와 사용할 모델 이름.
    base_url: str = "https://llm.sdc.siemens.cloud/v1"
    llm_model: str = ""
    # 호출 경로를 직접 지정할 수 있으며, 비어 있으면 모델 카탈로그에서 찾는다.
    llm_base_path: str = ""
    # LLM HTTP 클라이언트에 적용할 타임아웃(초).
    llm_timeout_seconds: float = 60.0
    # auto는 json_schema → json_object → prompt 순서로 구조화 출력을 시도한다.
    llm_json_mode: Literal["auto", "json_schema", "json_object", "prompt"] = "auto"

    # 실제 결함률 예측 API의 주소와 인증 키.
    ai_hub_endpoint_url: str = ""
    ai_hub_api_key: str = ""
    # 인증 키가 있으면 기본적으로 Authorization: Bearer <키> 형태로 전송한다.
    ai_hub_auth_header: str = "Authorization"
    ai_hub_auth_scheme: str = "Bearer"
    # 응답에서 레코드 배열과 퍼센트 단위의 예측값을 찾는 데 사용하는 키.
    ai_hub_response_key: str = "data"
    ai_hub_prediction_column: str = "prediction(defect_rate_pct)"
    # HTTPS 서버 인증서 검증은 기본적으로 활성화한다.
    ai_hub_verify_ssl: bool = True
    # 전송한 입력 컬럼이 응답 에코에 누락되면 오류로 처리한다.
    # 컬럼 존재 여부만 검사하며, 요청과 응답 값의 동일성을 보장하지는 않는다.
    ai_hub_strict_echo: bool = True
    # 예측 API HTTP 클라이언트의 타임아웃(초)과 최초 호출 이후 추가 재시도 횟수.
    ai_hub_timeout_seconds: float = 30.0
    ai_hub_max_retries: int = 2

    # ML API 호출만 더미 예측으로 대체한다. 질의 추출용 LLM은 계속 사용한다.
    mock_ml: bool = False
    # API와 CLI에서 로깅 초기화 시 사용하는 로그 수준.
    log_level: str = "INFO"

    @property
    def api_origin(self) -> str:
        """기본 URL에서 경로를 제외한 스킴과 호스트(포트 포함)를 반환한다."""
        # 예: https://example.com/v1 → https://example.com
        p = urlsplit(self.base_url)
        return f"{p.scheme}://{p.netloc}"

    def validate_runtime(self) -> None:
        """필수 설정의 누락을 모아 RuntimeError로 보고한다."""
        # 설정의 존재 여부만 확인하며 인증 성공이나 서비스 연결 여부는 검사하지 않는다.
        errors: list[str] = []
        if not self.api_key:
            errors.append("api_key 가 없습니다.")
        if not self.llm_model:
            errors.append("LLM_MODEL 이 없습니다.")
        # 모의 ML 모드에서는 실제 예측 엔드포인트 주소를 생략할 수 있다.
        if not self.mock_ml and not self.ai_hub_endpoint_url:
            errors.append("ai_hub_endpoint_url 이 없습니다.")
        if errors:
            raise RuntimeError(".env 설정 오류:\n- " + "\n- ".join(errors))


# 설정을 프로세스 내에서 재사용하여 환경 변수와 .env를 반복해서 읽지 않는다.
# 변경된 환경을 반영하려면 get_settings.cache_clear() 호출 또는 재시작이 필요하다.
@lru_cache
def get_settings() -> Settings:
    """최초 호출 시 설정을 로드하고 이후에는 캐시된 인스턴스를 반환한다."""
    return Settings()
