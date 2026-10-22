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
| `test_core.py` | 스키마, 슬롯 필링, ML 응답 파싱, 골든 G01/G10. LLM·HTTP 없음 |
| `curl_test.sh` | ML 엔드포인트 스모크 curl |

## 데이터·문서

| 경로 | 역할 |
| --- | --- |
| `data/golden_set.json` | 추출/검증 기대값 (G01–G14, M01–M03) |
| `docs/architecture.md` | 파이프라인 설계 |
| `docs/input_schema.md` | 12개 입력 필드 |
| `docs/run.md` | pytest 설명, CLI/HTTP/curl 실행 가이드 |
