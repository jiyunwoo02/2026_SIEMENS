"use strict";

/** 로컬 UI 모듈: DOM 입력을 대화 API에 보내고 JSON 응답을 텍스트로 표시한다. */
(() => {
  const ui = Object.fromEntries(
    [
      "chat-form",
      "query",
      "send",
      "reset",
      "explain",
      "example-full",
      "example-partial",
      "messages",
      "health",
      "progress",
      "error",
      "session",
      "result-status",
      "predictions",
      "missing",
      "known",
      "raw",
      "latency",
    ].map((id) => [id, document.getElementById(id)]),
  );
  const statuses = {
    // [수정] 2026-10-22: 상태를 한눈에 구분할 수 있도록 모든 상태 문구 앞에 이모지 추가 (UI 문구만 변경, 로직 변경 없음)
    ok: "✅ 예측 완료",
    need_more_info: "📝 추가 입력이 필요합니다 (ML 미호출)",
    invalid_input: "⚠️ 입력값 검증 실패 (ML 미호출)",
    endpoint_error: "❌ ML API 처리 오류",
    llm_error: "🤖 자연어 해석 오류 (ML 미호출)",
  };
  const fullExample =
    "LINE-BPR-01 주간조에서 SIM-SUP-B 자재로 533개 생산 예정입니다. " +
    "작업장 습도는 54.49%, 입고 자재 품질점수 83.95, 코팅 목표두께 79.22um, " +
    "용접 에너지 설정 92.67%, 지그 정렬 오프셋 0.112mm, 공정 설정편차 13.06%, " +
    "공구 마모도 14.41%이고 마지막 정비 후 30일 지났습니다. 결함률 예측해주세요.";
  // [추가] 2026-10-22: 사용자가 어떤 값을 입력해야 하는지 알 수 있도록 안내 문구를 상수로 분리했다.
  // 최초 로드와 새 대화 시작 두 곳에서 같은 문구를 쓴다. 항목명·허용값은 schema.py의 FIELD_SPEC과
  // 수동으로 맞춘 것이므로, 스키마가 바뀌면 이 문구도 함께 수정해야 한다.
  const welcomeMessage = [
    "결함률 예측에는 아래 12개 값이 필요합니다. 한 번에 입력하거나 나눠서 입력해도 됩니다.",
    "",
    "• 생산 라인: LINE-BPR-01, LINE-BPR-02",
    "• 교대조: 주간(DAY) / 야간(NIGHT)",
    "• 공급사 코드: SIM-SUP-A, SIM-SUP-B, SIM-SUP-C",
    "• 계획 생산 수량(개)",
    "• 작업장 습도(%)",
    "• 입고 자재 품질점수",
    "• 코팅 목표 두께(um)",
    "• 용접 에너지 설정(%)",
    "• 지그 정렬 오프셋(mm)",
    "• 공정 설정 편차(%)",
    "• 공구 마모도(%)",
    "• 마지막 정비 후 경과 일수",
    "",
    '라인 등 일부 값만 바꿔 여러 조건을 비교할 수도 있습니다. 예: "LINE-BPR-01과 02 비교"',
    "부족한 값은 추가 질문으로 안내합니다. 전체 조건 예제 버튼으로 입력 형식을 확인할 수 있습니다.",
  ].join("\n");
  // 세션 ID와 대화는 탭 메모리에만 보관한다. 새로고침하면 복원하지 않는다.
  let sessionId = null;
  let busy = false;

  // [추가] 메시지 종류별 아바타 이모지. 별도 이미지 파일 없이 구분 가능하도록 이모지를 사용한다.
  // 디자인을 바꾸고 싶으면 이 두 값만 수정하면 된다.
  const avatarByKind = { user: "🙂", assistant: "🤖" };

  /** 문자열과 종류를 받아 HTML 해석 없이 대화 로그에 메시지를 추가한다. */
  function addMessage(kind, text) {
    const article = document.createElement("article");
    article.className = `message ${kind}`;

    // [수정] 사용자/AI 메시지를 한눈에 구분할 수 있도록 아바타(이모지)를 추가했다.
    // 이름(heading)으로 이미 구분되므로 스크린리더에는 중복 안내하지 않게 aria-hidden 처리.
    const avatar = document.createElement("span");
    avatar.className = "message-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = avatarByKind[kind] ?? "💬";

    const content = document.createElement("div");
    content.className = "message-content";
    const heading = document.createElement("strong");
    heading.textContent = kind === "user" ? "나" : "AIHUB";
    const body = document.createElement("p");
    body.textContent = text;
    content.append(heading, body);

    article.append(avatar, content);
    ui.messages.append(article);
    article.scrollIntoView({ block: "nearest" });
  }

  /** 처리 여부와 안내문을 받아 중복 전송/처리 중 초기화를 방지한다. */
  function setBusy(value, message = "") {
    busy = value;
    for (const id of [
      "send",
      "reset",
      "query",
      "explain",
      "example-full",
      "example-partial",
    ]) {
      ui[id].disabled = value;
    }
    ui["chat-form"].setAttribute("aria-busy", String(value));
    ui.progress.textContent = message;
  }

  /** 오류 문자열을 표시한다. 빈 문자열이면 경고 영역을 숨긴다. */
  function showError(message = "") {
    ui.error.textContent = message;
    ui.error.hidden = !message;
  }

  /** 경로/옵션을 받아 JSON을 반환한다. HTTP·연결·JSON 오류는 Error로 전달한다. */
  async function request(path, options = {}) {
    let response;
    try {
      response = await fetch(path, { cache: "no-store", ...options });
    } catch (error) {
      throw new Error(
        error.name === "AbortError"
          ? "서버 설정 확인 시간이 초과되었습니다."
          : "서버에 연결할 수 없습니다. 서버 실행 여부와 네트워크를 확인하세요.",
      );
    }
    // 삭제 대상이 이미 없으면 새 대화 시작에 지장이 없다.
    if (options.method === "DELETE" && response.status === 404) return null;
    let body;
    try {
      body = await response.json();
    } catch {
      throw new Error(
        `HTTP ${response.status}: JSON 응답이 아닙니다. 서버 로그를 확인하세요.`,
      );
    }
    if (!response.ok) {
      const detail =
        typeof body?.detail === "string"
          ? body.detail
          : "요청을 처리하지 못했습니다.";
      throw new Error(`HTTP ${response.status}: ${detail}`);
    }
    return body;
  }

  /** 최신 결과 영역을 비워 이전 예측값이 새 요청의 결과로 보이지 않게 한다. */
  function clearResult() {
    ui.predictions.replaceChildren();
    ui.missing.replaceChildren();
    const item = document.createElement("li");
    item.textContent = "아직 확인하지 않았습니다.";
    ui.missing.append(item);
    ui.known.textContent = "{}";
    ui.raw.textContent = "{}";
    ui.latency.textContent = "";
  }

  /** API 응답 객체를 받아 세션·상태·퍼센트 예측값·상세 JSON을 표시한다. */
  function renderResult(body) {
    ui.raw.textContent = JSON.stringify(body, null, 2);
    if (
      !body ||
      !Object.hasOwn(statuses, body.status) ||
      typeof body.answer !== "string" ||
      typeof body.session_id !== "string" ||
      !body.session_id
    ) {
      throw new Error(
        "대화 API 응답 형식이 예상과 다릅니다. 상세 응답 JSON을 확인하세요.",
      );
    }
    sessionId = body.session_id;
    ui.session.textContent = `세션 ${sessionId} · 처리 턴 ${body.turn}`;
    ui["result-status"].textContent =
      `${statuses[body.status]} · ${body.status}`;
    const predictions = Array.isArray(body.predictions) ? body.predictions : [];
    predictions.forEach((value, index) => {
      const card = document.createElement("div");
      card.className = "prediction";
      // API 값은 이미 퍼센트 단위이므로 100을 곱하지 않는다.
      card.textContent = `조건 ${index + 1}: ${
        typeof value === "number" && Number.isFinite(value)
          ? `${value.toFixed(2)}%`
          : "유효하지 않은 예측값"
      }`;
      ui.predictions.append(card);
    });
    ui.missing.replaceChildren();
    const missing = Array.isArray(body.missing_fields)
      ? body.missing_fields
      : [];
    for (const field of missing.length
      ? missing
      : [
          body.status === "ok"
            ? "없음"
            : "보고된 누락 항목 없음 (답변과 오류 내용을 확인하세요)",
        ]) {
      const item = document.createElement("li");
      item.textContent = field;
      ui.missing.append(item);
    }
    ui.known.textContent = JSON.stringify(body.known_slots || {}, null, 2);
    if (body.status === "ok") {
      ui.latency.textContent = `ML 클라이언트 보고 시간: ${body.latency_ms} ms (전체 처리 시간 아님)`;
    }
    if (
      ["endpoint_error", "llm_error", "invalid_input"].includes(body.status)
    ) {
      showError(
        Array.isArray(body.errors) && body.errors.length
          ? body.errors.join("\n")
          : body.answer,
      );
    }
    addMessage("assistant", body.answer);
  }

  /** 폼 제출을 받아 같은 탭의 세션으로 한 번만 요청한다. 실패 시 입력을 보존한다. */
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const query = ui.query.value.trim();
    if (!query) {
      showError("질의를 입력해주세요.");
      ui.query.focus();
      return;
    }
    showError();
    clearResult();
    ui["result-status"].textContent = "🤖 현재 질의 처리 중…";
    addMessage("user", query);
    setBusy(
      true,
      "LLM 해석 및 필요한 경우 ML 예측을 처리 중입니다. 수 분 걸릴 수 있습니다.",
    );
    const started = performance.now();
    try {
      const body = await request("/chat/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          session_id: sessionId,
          explain: ui.explain.checked,
        }),
      });
      renderResult(body);
      if (["ok", "need_more_info"].includes(body.status)) ui.query.value = "";
      ui.progress.textContent = `전체 응답 시간: ${((performance.now() - started) / 1000).toFixed(1)}초`;
    } catch (error) {
      const message = `${error.message} 자동 재전송하지 않습니다. 연결이 끊겼어도 서버 처리는 진행됐을 수 있습니다.`;
      showError(message);
      ui["result-status"].textContent =
        "요청 실패 · 현재 질의의 결과를 확인하지 못했습니다.";
      addMessage("assistant", message);
      ui.progress.textContent = "";
    } finally {
      setBusy(false, ui.progress.textContent);
      ui.query.focus();
    }
  }

  /** 현재 서버 세션을 삭제하고 화면을 초기화한다. 삭제 실패 시 기존 대화를 보존한다. */
  async function reset() {
    if (busy) return;
    showError();
    setBusy(true, "대화 초기화 중…");
    try {
      if (sessionId)
        await request(`/chat/session/${encodeURIComponent(sessionId)}`, {
          method: "DELETE",
        });
      sessionId = null;
      ui.messages.replaceChildren();
      clearResult();
      ui.query.value = "";
      ui.session.textContent = "새 세션 · 아직 질의하지 않았습니다.";
      ui["result-status"].textContent = "질의를 보내면 결과가 표시됩니다.";
      // [수정] 2026-10-22: 짧은 문구 대신 필요 입력 항목 안내(welcomeMessage)를 표시한다.
      addMessage("assistant", `새 대화입니다.\n${welcomeMessage}`);
    } catch (error) {
      showError(`대화 초기화 실패: ${error.message} 기존 대화는 유지했습니다.`);
    } finally {
      setBusy(false);
      ui.query.focus();
    }
  }

  /** 설정 상태만 조회해 실제 ML/모의 ML 여부를 표시한다. 외부 연결 검사는 아니다. */
  async function checkHealth() {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
      const health = await request("/health", { signal: controller.signal });
      const missing = [];
      if (!health.llm_configured) missing.push("LLM 키 또는 모델");
      if (!health.mock_ml && !health.endpoint_configured)
        missing.push("ML 엔드포인트");
      ui.health.className = `notice ${missing.length || health.mock_ml ? "warning" : "ready"}`;
      const mode = health.mock_ml
        ? "모의 ML: 더미 예측값 (실제 ML 미호출)"
        : "실제 ML API 모드";
      ui.health.textContent =
        `${mode} · ${missing.length ? `설정 누락: ${missing.join(", ")}` : "필수 설정 있음"}` +
        " · LLM은 실제 호출 · 외부 서비스 연결은 검사하지 않았습니다.";
    } catch (error) {
      ui.health.className = "notice warning";
      ui.health.textContent = `${error.message} 설정 상태를 확인하지 못했습니다. 새로고침해 다시 확인하세요.`;
    } finally {
      clearTimeout(timer);
    }
  }

  /** 예제 문자열을 입력란에만 채운다. API 호출이나 세션 초기화는 하지 않는다. */
  function fillExample(text) {
    if (busy) return;
    ui.query.value = text;
    ui.query.focus();
  }

  ui["chat-form"].addEventListener("submit", submit);
  ui.reset.addEventListener("click", reset);
  ui["example-full"].addEventListener("click", () => fillExample(fullExample));
  ui["example-partial"].addEventListener("click", () =>
    fillExample("LINE-BPR-01 결함률 예측해줘"),
  );
  // [수정] 2026-10-22: 최초 메시지에도 필요 입력 항목 안내를 표시한다.
  addMessage("assistant", `🤖 생산 조건을 알려주세요.\n${welcomeMessage}`);
  checkHealth();
})();
