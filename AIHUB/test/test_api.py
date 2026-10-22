"""로컬 UI 라우트와 대화 API 계약 테스트. 외부 LLM/ML 호출은 테스트 대역으로 대체한다."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from aihub import api
from aihub.pipeline import PipelineResult


class FakePipeline:
    """질의/세션/해설 플래그를 기록하고 지정된 상태의 고정 응답을 반환한다."""

    def __init__(self):
        self.calls = []
        self.status = "need_more_info"

    def run(self, query, *, session, explain):
        """요청을 기록하고 실제 SlotFillingSession을 갱신해 멀티턴 계약을 검증한다."""
        self.calls.append((query, session.session_id, explain))
        session.merge([{"production_line": "LINE-BPR-01"}])
        return PipelineResult(
            status=self.status,
            answer="<script>외부 응답도 텍스트로 표시해야 합니다.</script>",
            known_slots=session.known(),
            missing_fields=session.missing() if self.status == "need_more_info" else [],
            predictions=[1.65, 2.65] if self.status == "ok" else [],
            errors=["테스트 오류"] if self.status.endswith("error") else [],
        )


@pytest.fixture
def client(monkeypatch):
    """설정과 세션을 격리한 TestClient를 제공한다. 실제 서비스에 접속하지 않는다."""
    monkeypatch.setattr(api, "_sessions", {})
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(
        mock_ml=False, ai_hub_endpoint_url="https://example.invalid/predict",
        api_key="test-only-not-a-secret", llm_model="test-model",
    ))
    with TestClient(api.app) as test_client:
        yield test_client


@pytest.fixture
def predictor(monkeypatch):
    """실제 파이프라인 생성 대신 상태를 제어할 수 있는 대역을 반환한다."""
    fake = FakePipeline()
    monkeypatch.setattr(api, "pipeline", lambda: fake)
    return fake


def test_ui_assets_without_pipeline(client, monkeypatch):
    """HTML/JS/CSS 제공은 LLM/ML 초기화 없이 가능하며 잘못된 경로는 404이다."""
    def forbidden():
        """정적 파일 요청 중 파이프라인 호출을 감지하면 실패시킨다."""
        raise AssertionError("정적 UI는 파이프라인을 초기화하면 안 됩니다.")

    monkeypatch.setattr(api, "pipeline", forbidden)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '/ui-assets/app.js' in response.text
    assert 'id="latency"' in response.text
    for asset, mime in [("app.js", "javascript"), ("style.css", "text/css")]:
        result = client.get(f"/ui-assets/{asset}")
        assert result.status_code == 200
        assert mime in result.headers["content-type"]
    assert client.get("/ui-assets/missing.js").status_code == 404
    assert client.get("/ui-assets/%2e%2e/config.py").status_code == 404
    assert client.get("/ui-assets/.env").status_code == 404


@pytest.mark.parametrize("mock, key, model, endpoint, llm_ok", [
    (False, "test", "model", "https://example.invalid", True),
    (True, "", "model", "", False),
    (False, "test", "", "", False),
])
def test_health_configuration_only(client, monkeypatch, mock, key, model, endpoint, llm_ok):
    """health는 설정 여부만 반환하며 인증 키나 엔드포인트 원문을 노출하지 않는다."""
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(
        mock_ml=mock, api_key=key, llm_model=model, ai_hub_endpoint_url=endpoint,
    ))
    assert client.get("/health").json() == {
        "status": "ok", "mock_ml": mock, "endpoint_configured": bool(endpoint),
        "llm_configured": llm_ok, "active_sessions": 0,
    }


def test_chat_continue_and_reset(client, predictor):
    """session_id 재사용, explain 전달, 세션 삭제/404와 새 세션 생성을 검증한다."""
    first = client.post("/chat/predict", json={"query": "첫 질의", "explain": False}).json()
    sid = first["session_id"]
    assert first["turn"] == 1
    assert first["status"] == "need_more_info"
    assert first["known_slots"] == {"production_line": "LINE-BPR-01"}
    second = client.post("/chat/predict", json={"query": "추가 입력", "session_id": sid}).json()
    assert second["session_id"] == sid
    assert second["turn"] == 2
    assert predictor.calls == [("첫 질의", sid, False), ("추가 입력", sid, True)]
    assert client.get("/health").json()["active_sessions"] == 1
    assert client.delete(f"/chat/session/{sid}").json() == {"status": "reset", "session_id": sid}
    assert client.delete(f"/chat/session/{sid}").status_code == 404
    assert client.get("/health").json()["active_sessions"] == 0
    third = client.post("/chat/predict", json={"query": "새 질의"}).json()
    assert third["session_id"] != sid
    assert third["turn"] == 1


@pytest.mark.parametrize("status", ["ok", "need_more_info", "invalid_input", "llm_error", "endpoint_error"])
def test_pipeline_status_passthrough(client, predictor, status):
    """HTTP 성공과 별개인 처리 상태, 예측 단위 및 오류 정보를 그대로 전달한다."""
    predictor.status = status
    response = client.post("/chat/predict", json={"query": "질의"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == status
    assert body["unit"] == "percent"
    assert body["predictions"] == ([1.65, 2.65] if status == "ok" else [])
    assert "errors" in body


@pytest.mark.parametrize("payload", [{}, {"query": ""}, {"query": "  \n "}, {"query": None}])
def test_reject_empty_query(client, predictor, payload):
    """빈 질의와 공백 질의는 파이프라인/세션 생성 전에 422로 차단한다."""
    assert client.post("/chat/predict", json=payload).status_code == 422
    assert not predictor.calls
    assert not api._sessions


def test_configuration_failure_json(client, monkeypatch):
    """초기화 실패를 민감한 예외 원문 없이 503 JSON으로 전달한다."""
    def unavailable():
        """런타임 설정 누락을 외부 연결 없이 재현한다."""
        raise RuntimeError("test-only-private-detail")

    monkeypatch.setattr(api, "pipeline", unavailable)
    response = client.post("/chat/predict", json={"query": "질의"})
    assert response.status_code == 503
    assert "환경 설정" in response.json()["detail"]
    assert "test-only-private-detail" not in response.text
    assert not api._sessions
