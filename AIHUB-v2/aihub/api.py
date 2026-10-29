from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import get_settings
from .pipeline import DefectRatePipeline, SlotFillingSession

# 설정에 지정된 로그 수준을 적용하고 시간, 로그 수준, 로거 이름을 함께 출력한다.
logging.basicConfig(
    level=get_settings().log_level, format="%(asctime)s %(levelname)s %(name)s | %(message)s"
)

# 불량률 예측 대화를 제공하는 FastAPI 애플리케이션.
app = FastAPI(title="AIHUB Defect Rate Assistant", version="1.0.0")

# [수정] 로컬 UI와 API를 같은 출처에서 제공해 별도 프런트 서버/CORS 설정을 없앤다.
_WEB_DIR = Path(__file__).resolve().parent / "web"
app.mount("/ui-assets", StaticFiles(directory=_WEB_DIR), name="ui-assets")


@app.get("/", response_class=FileResponse, include_in_schema=False)
def index() -> FileResponse:
    """입력 없이 로컬 질의 화면 HTML을 반환한다. 외부 서비스를 호출하지 않는다."""
    return FileResponse(_WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})

# 파이프라인은 최초 사용 시 생성하여 현재 프로세스에서 재사용한다.
_pipeline: DefectRatePipeline | None = None

# 세션별 슬롯 수집 상태를 메모리에 보관한다.
# 프로세스 재시작 시 초기화되며, 여러 워커 사이에서는 공유되지 않는다.
_sessions: dict[str, SlotFillingSession] = {}


def pipeline() -> DefectRatePipeline:
    """예측 파이프라인을 지연 초기화하고 저장된 인스턴스를 반환한다."""
    global _pipeline
    if _pipeline is None:
        _pipeline = DefectRatePipeline()
    return _pipeline


class ChatRequest(BaseModel):
    """예측 대화 요청 본문과 기본값을 정의한다."""

    # 사용자 입력은 최소 한 글자 이상이어야 한다.
    query: str = Field(min_length=1)
    # 기존 세션 ID를 전달하면 대화를 이어가고, 생략하면 새 ID를 생성한다.
    session_id: str | None = None
    # 예측 결과에 대한 설명 생성 여부를 파이프라인에 전달한다.
    explain: bool = True


@app.get("/health")
def health() -> dict[str, object]:
    """현재 설정과 메모리에 보관된 세션 수를 반환한다."""
    # 엔드포인트 URL 설정 여부만 확인하며, 외부 서비스 연결을 검사하지는 않는다.
    s = get_settings()
    return {
        "status": "ok",
        "mock_ml": s.mock_ml,
        "endpoint_configured": bool(s.ai_hub_endpoint_url),
        # [수정] UI에 설정 누락 여부만 알리고 키/모델명/외부 URL은 노출하지 않는다.
        "llm_configured": bool(s.api_key and s.llm_model),
        "active_sessions": len(_sessions),
    }


@app.post("/chat/predict")
def chat_predict(req: ChatRequest) -> dict[str, object]:
    """세션 상태를 이용해 사용자 입력을 처리하고 예측 대화 결과를 반환한다."""
    # [수정] 공백 질의를 차단하고 설정 오류를 UI가 읽을 수 있는 JSON으로 반환한다.
    if not req.query.strip():
        raise HTTPException(status_code=422, detail="질의를 입력해주세요.")
    try:
        predictor = pipeline()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="예측 서비스를 초기화할 수 없습니다. 서버의 LLM/ML 환경 설정을 확인하세요.",
        ) from exc
    # 세션 ID가 없거나 빈 문자열이면 UUID에서 12자리 식별자를 생성한다.
    sid = req.session_id or uuid.uuid4().hex[:12]
    # 등록된 세션을 사용하고, 해당 ID가 없으면 새 세션을 저장한다.
    session = _sessions.setdefault(sid, SlotFillingSession(session_id=sid))
    # 슬롯 수집 및 예측 처리는 파이프라인에 위임한다.
    result = predictor.run(req.query, session=session, explain=req.explain)
    # 다음 요청에서 대화를 이어갈 수 있도록 세션 ID와 처리 후 턴 정보를 포함한다.
    body = result.to_dict()
    body["session_id"] = sid
    body["turn"] = session.turn
    return body


@app.delete("/chat/session/{session_id}")
def reset_session(session_id: str) -> dict[str, str]:
    """메모리에서 지정한 세션을 삭제하고, 없는 세션이면 404를 반환한다."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="session not found")
    _sessions.pop(session_id)
    return {"status": "reset", "session_id": session_id}
