# 코드 목록 (Code Inventory)

패키지는 프로젝트 루트의 `aihub/` 입니다. import는 `from aihub.pipeline import DefectRatePipeline` 형태입니다.

실행·테스트 방법과 pytest 설명은 [`run.md`](./run.md)를 참고합니다.

## 패키지 `aihub/`

| 파일 | 역할 |
| --- | --- |
| `config.py` | `.env` 설정 (SDC LLM, ML 엔드포인트, `MOCK_ML`) |
| `schema.py` | 12개 필드 정의, `DefectRateInput` 검증, 추출 JSON Schema, payload |
| `llm.py` | SDC LLM 클라이언트 + 추출/해설 프롬프트 |
| `ml.py` | 결함률 예측 API 클라이언트 (재시도, 에코 검증) |
| `pipeline.py` | 추출·세션 병합·검증·예측·해설 |
| `api.py` | FastAPI: `/health`, `/chat/predict`, 세션 삭제 |
| `cli.py` | 한 줄/대화형 CLI (`python -m aihub`) |

## 테스트 (`test/`)

| 파일 | 역할 |
| --- | --- |
| `test_core.py` | 스키마, 슬롯 필링, ML 응답 파싱, 골든 v2 C01/I01. LLM·HTTP 없음 |
| `test_golden_v2.py` | 골든 v2 전체 케이스: 데이터 규칙 일관성, 추출 이후 판정(status·missing·ambiguous·invalid·payload), 멀티턴 기대 payload, 추출 후처리·스키마·프롬프트. LLM 추출은 대역(실제 LLM 추출 정확도는 미검증) |
| `test_api.py` | 정적 UI 라우트와 대화 API 계약. 파이프라인은 대역 |
| `curl_test.sh` | ML 엔드포인트 스모크 curl |

## 데이터·문서

| 경로 | 역할 |
| --- | --- |
| `data/golden_set_v2.json` | 추출/검증 기대값 v2.0 (C01–C10, P01–P08, N01–N05, A01–A07, I01–I05, MT01–MT06) |
| `data/v1/golden_set.json` | 이전 버전 v1.1 (G01–G14, M01–M03) |
| `docs/architecture.md` | 파이프라인 설계 |
| `docs/input_schema.md` | 12개 입력 필드 |
| `docs/run.md` | pytest 설명, CLI/HTTP/curl 실행 가이드 |
