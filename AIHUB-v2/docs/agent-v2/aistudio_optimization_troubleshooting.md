# Altair AI Studio 최적화 프로세스 구축 및 트러블슈팅 기록

## 1. 목표

사용자가 목표 변수(`target`)를 API로 입력하면, 해당 값을 기준으로 Prescriptive Analytics 최적화를 수행하고 최적 입력값을 반환한다.

- 환경: Altair AI Studio 2026.1.1 / Altair AI Hub (엔드포인트 배포)
- 모델: GBT 분류 모델 (라벨: `high_defect_flag`, 클래스 `0` / `1`)
- 핵심 오퍼레이터: Prescriptive Analytics (진화적 최적화), 매크로

---

## 2. 최종 동작 구성

```
Retrieve data → Map → Set Label → Sample → Prescriptive Analytics (tra)
GBT 분류 (Retrieve model) ───────────────→ Prescriptive Analytics (mod)
```

| 항목 | 설정 |
|---|---|
| Context 매크로 | `target = 1` (View → Show Panel → Context) |
| class name | `%{target}` |
| classification | 체크 |
| optimization direction | minimize |
| limit type | generations and population size (population 10, max generations 5) 또는 time limit |
| 입력 범위 제한 | stay above global minimum / below global maximum 체크 |
| Process output | result 1 ← Prescriptive Analytics의 optimal data |

---

## 3. 문제 해결 과정

| # | 증상 | 시도 / 조치 | 결과 |
|---|---|---|---|
| 1 | Set Macro의 값이 비어 있어, 외부 입력을 덮어쓸 우려 | Set Macro 제거, **Context 패널에 매크로 정의** (기본값 포함) | Set Macro는 기존 매크로를 재정의하므로 외부 값을 덮어쓸 수 있음. Context 방식으로 변경 |
| 2 | Run을 눌러도 아무것도 진행되지 않음 | AI Studio 창을 닫고 다시 실행 | 이후 breakpoint 정상 동작. 이전 실행이 남아 있었던 것으로 추정 |
| 3 | Prescriptive Analytics에서 무한 로딩 | time limit 30초 설정 | 해결 안 됨 |
| 4 | 위와 동일 | generations/population을 최소(5/10)로, 데이터를 10행으로 샘플링 | 해결 안 됨 → 데이터 크기·탐색 규모는 원인이 아님 |
| 5 | 위와 동일 | GBT를 Random Forest로 교체 | 해결 안 됨 → 모델 종류는 원인이 아님 |
| 6 | 원핫 인코딩 버전 | 모델 학습 데이터와 컬럼이 달라 에러 | 원핫 인코딩은 사용하지 않기로 함 |
| 7 | 아래쪽 비활성 프로세스는 정상 | 매크로 없이 `class name = 1`, minimize | 결과 정상 출력 → 기준선(baseline) 확보 |
| 8 | 라벨 값 불일치 가설 (`abnormal` vs `0/1`) | `tra`에만 Map을 적용해도 정상 동작함을 확인 | **가설 기각.** `tra`의 라벨 값은 영향 없음 |
| 9 | Context에 `target = 1`이 있어도 `class name = 1`이면 정상 | 정상 프로세스에서 `class name`을 `%{target}`으로만 변경 | **정상 동작** |

### 원인을 확정하지 못한 부분

- 위쪽 프로세스가 멈췄던 정확한 원인은 특정하지 못했다.
- 정상 동작하는 프로세스를 기준으로 **한 번에 하나씩** 변경하며 실행하는 방식으로 정상 상태에 도달했다.
- 매크로(`%{target}`) 치환 자체는 문제가 아니었다.

---

## 4. 배포 및 API 테스트

```bash
URL="https://<AI Hub 주소>/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization"

curl -G -s --max-time 180 "$URL" --data-urlencode "target=1" | python -m json.tool > out_1.json
curl -G -s --max-time 180 "$URL" --data-urlencode "target=0" | python -m json.tool > out_0.json
diff out_1.json out_0.json
```

| target | 의미 | 결과 |
|---|---|---|
| `1` | 불량(1) 확률 최소화 | `confidence(1)` ≈ 1.7%, 예측 `0` |
| `0` | 정상(0) 확률 최소화 | `confidence(0)` ≈ 1.7%, 예측 `1` |

두 호출의 결과가 서로 달라, **쿼리 파라미터가 매크로로 정상 전달됨**을 확인했다. (기본값과 같은 값만 호출하면 반영 여부를 알 수 없으므로 반드시 다른 값으로 비교할 것)

---

## 5. 배운 점 (체크리스트)

- 외부 입력용 매크로는 **Set Macro가 아니라 Context 패널**에서 정의한다. (Set Macro는 기존 값을 덮어쓴다)
- Prescriptive Analytics의 `class name`은 **모델이 아는 클래스 값**(`0`/`1`)과 일치해야 한다.
- 종료 조건(`limit type`)을 반드시 설정한다.
- 원인을 모를 때는 **작동하는 프로세스를 복사한 뒤 한 가지씩만 변경**해서 멈추는 지점을 찾는다.
- 실행이 멈추면 Stop → 안 되면 Studio 재시작.
- API 테스트는 **기본값과 다른 값**으로 호출해 매크로 반영을 검증한다.
- 모델 학습 데이터와 `tra` 데이터의 컬럼 구성은 맞춰야 한다.

---

## 6. 남은 과제

- [ ] 같은 요청을 여러 번 호출했을 때 결과가 안정적인지 확인 (필요 시 `use local random seed`)
- [ ] 조절할 수 없는 변수(`shift`, `supplier_code`, `planned_quantity`, `ambient_humidity_pct` 등)를 `constant attribute values`로 고정할지 검토
- [ ] 응답 시간 측정 및 최적화 상한 조정
- [ ] 잘못된 입력(`target=abc`, 파라미터 누락) 처리 확인
- [ ] 엔드포인트 접근 제어(인증) 점검
- [ ] 테스트용 Sample 크기와 최적화 품질 재검토
- [ ] 사용자 입력 형식을 `normal`/`abnormal`로 받을지 결정
