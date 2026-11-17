# Altair AI Platform 학습 문서

Altair(구 RapidMiner) AI Platform의 세 가지 핵심 도구에 대한 학습 문서 모음입니다.  
이 프로젝트에서 실제로 사용한 작업물을 예시로 참조합니다.

---

## 도구 한눈에 보기

| 도구 | 역할 | 주요 파일 형식 |
|------|------|----------------|
| **AI Studio** | 데이터 전처리 · 모델 학습 · 배포 프로세스 설계 | `.rmp`, `.rmmodel`, `.rmtabmod` |
| **AI Hub** | 학습된 모델을 REST API로 서빙 | JSON 요청/응답 |
| **Panopticon** | 대시보드 시각화 · Python Transform으로 API 호출 | `.exz`, `datatable.json`, `dashboard.json` |

---

## 전체 파이프라인

```
[AI Studio]            [AI Hub]               [Panopticon]
모델 학습 (.rmp)  →   REST API 엔드포인트  →  대시보드 시각화
                       스냅샷 배포              Python Transform
                                                슬라이더 · 드롭다운 UI
```

---

## 목차

| 문서 | 내용 |
|------|------|
| [`01_ai_studio.md`](01_ai_studio.md) | AI Studio 개요, 화면 구성, 학습 프로세스, 파일 형식 |
| [`02_ai_hub.md`](02_ai_hub.md) | AI Hub 개요, 배포 절차, REST API 호출 방법 |
| [`03_panopticon.md`](03_panopticon.md) | Panopticon 개요, 대시보드 구성 요소, Python Transform |
| [`04_full_pipeline.md`](04_full_pipeline.md) | 세 도구를 연결한 전체 파이프라인 흐름 |

---

## 이 프로젝트에서 사용한 사례

| 프로젝트 | AI Studio | AI Hub | Panopticon |
|---------|-----------|--------|------------|
| `hd-modeling/` | GBT 회귀·분류 모델 학습 | 결함률 예측 · 최적화 API 배포 | `defect-dashboard/` |
| `nice-modeling/` | LightGBM 신용평가 모델 학습 | 신용점수 스코어링 API 배포 | NICE 대시보드 |
