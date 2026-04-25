# 미해결 질문들 (Open Questions)

🇺🇸 English: [../../open-questions.md](../../open-questions.md) · 🤖 AI/LLM: [../open-questions.ai.md](../open-questions.ai.md)

이 문서는 저자들이 알고 있는 미해결 설계 질문들을 나열합니다.
일부는 미뤄도 되고, 일부는 향후 마일스톤의 blocking 항목입니다. 공개적으로 나열하는 데는 두 가지 목적이 있습니다: 외부 의견을 초대하고, 명세가 실제보다 더 확정된 것처럼 보이지 않도록 하는 것입니다.

각 질문에는 **status** 태그가 있습니다:

- **open** — 아직 명확한 답이 없음; 신중한 제안 환영
- **sketched** — 부분적 답이 있음, 검증 필요
- **deferred** — v0.1 출시에는 필요 없음; 이후 버전에서 blocking
- **resolved** — 해결됨

---

## 언어 수준 (Language-level)

### Q1. 이종 모델 간 confidence 합성 — *sketched*

서로 다른 language model은 서로 다른 calibration 특성을 갖습니다. 전략이 여러 모델에 대한 호출을 포함할 때 confidence는 어떻게 합산해야 할까요?

현재 spec은 결정론적 연산에는 최솟값을, 비결정론적 연산에는 calibrated self-report를 씁니다. 이는 보수적이지만 실제로는 너무 보수적일 수 있습니다 — 한 모델의 높은 confidence 답변이 다른 모델의 낮은 confidence 검사에 의해 불이익을 받아서는 안 됩니다.

가능한 방향:

- (intent, model) 쌍별 calibration에 메타-calibrator를 추가해 (model_id, raw_confidence) → 비교 가능한 confidence로 매핑.
- 각 모델을 독립적인 잡음 있는 추정치 생성기로 취급해 Bayesian update로 결합.
- intent별로 confidence 의미론을 선언해 서로 다른 intent가 다르게 합성될 수 있도록.

### Q2. 형식 의미론 (Formal semantics) — *open*

AIL은 현재 산문과 예제로 설명된 비형식적 운영 의미론만 가지고 있습니다. 표시적 의미론(denotational semantics)은 다음을 가능하게 합니다:

- 프로그램 동등성 검사 (이 evolved 버전이 선언된 bound 내에서 원본과 실제로 동등한가?)
- 컴파일러 최적화 (중복 intent 호출 접기 등)
- 런타임 준수의 형식 검증

아직 시작된 바 없습니다. 언어가 어느 정도 안정화된 후에야 가능한 대규모 작업입니다.

### Q3. 분포와 구간에 대한 타입 — *open*

명세는 `Distribution[T]`, `Interval[T]`, `Set[T]`를 일반 스칼라보다 풍부한 confidence 타입으로 도입하지만, 연산을 완전히 정의하지 않습니다. 이 타입들의 원칙적 설계 — 특히 `branch`와 constraint 만족과의 상호작용 — 는 미완성입니다.

### Q4. `in` 연산자와 컬렉션 멤버십 — *v0.1.1에서 해결됨*

~~MVP parser는 현재 `x in ["a", "b", "c"]`를 표현식으로 처리하지 못합니다 (`in`은 reserved keyword이지만 parser가 멤버십 표현식을 생성하지 않음). 명세는 이것이 작동해야 한다고 암시합니다; grammar는 `MembershipOp` production이 필요하고 executor는 매칭되는 평가 규칙이 필요합니다.~~

~~`classify.ail` 예제를 작성하면서 발견됨; 예제는 symbolic constraint로 우회합니다. 실제 프로그램은 이 연산자가 필요할 것입니다.~~

**해결:** `MembershipOp` AST 노드 추가; parser가 비교 우선순위에서 `x in C`와 `x not in C`를 인식합니다. executor는 Python `in`을 통해 평가하며, confidence 전파는 spec/03 §3.1에 따라 `min(element.confidence, collection.confidence)`입니다. `classify.ail`이 의도된 형태로 복원됐습니다. 5개의 새 executor 테스트가 연산자를 직접 및 branch arm을 통해 커버합니다.

---

## 런타임 수준 (Runtime-level)

### Q5. 크로스-런타임 evolution 동기화 — *deferred*

같은 AIL 프로그램이 두 런타임(예: prod + staging)에서 실행되고 그 중 하나가 intent를 evolve하면, 다른 쪽에도 전파되어야 할까요? 기본값은 아마: 기본적으로 아니오, 명시적 sync 선언이 있을 때 예. sync 프로토콜, 충돌 해결, rollback 조율은 미설계입니다.

### Q6. 적대적 입력과 calibration — *open*

입력을 통제하는 공격자는 체계적으로 거짓 피드백을 만들어 미래 calibration에 영향을 줄 수 있습니다. 현재 설계는 calibration의 견고성에 의존합니다; 더 강한 적대적 모델이 필요합니다.

가능한 방향:

- 인증된 피드백 채널 (서명된 피드백만 calibration을 업데이트).
- calibration 업데이트 이상 감지 (갑작스러운 ECE 변화에 플래그).
- 격리 가능한 소스별 calibrator.

### Q7. Strategy catalog 부트스트래핑 — *sketched*

명세는 dispatcher가 goal에 대한 후보 전략을 열거한다고 합니다. 초기 catalog는 어디서 오나요? 옵션:

- 배포별 수작업 (유연성 낮음, 신뢰 높음).
- `stdlib/*` 모듈 레지스트리에서 파생 (유연하지만 신중하게 큐레이션된 stdlib 필요).
- AI가 프로그램 자체로부터 생성 (메타적이며, 정렬 문제 제기).

참조 구현은 가장 단순한 옵션을 사용합니다 — intent당 하나의 전략, model adapter에 위임. 실제 AIRT는 더 필요합니다.

### Q8. 불확실성 하의 지연 시간 dispatch — *open*

제약 조건 `{ latency < 2000ms, fidelity > 0.9 }`이 주어졌을 때, dispatcher는 빠르고 저충실도인 전략과 느리고 고충실도인 전략 사이에서 선택해야 할 수 있습니다. 명세의 점수 규칙은 두 기댓값 분포가 잘 calibrated되었을 때 처리합니다. calibrated되지 않았거나 지연 시간 분포에 긴 꼬리가 있을 때 올바른 행동은 불명확합니다.

---

## OS 수준 (OS-level)

### Q9. 정책 충돌 해결 — *sketched*

여러 수준의 정책(운영자, 테넌트, 사용자, intent)이 충돌할 수 있습니다. 명세는 "하위 수준은 상위 수준이 거부한 것을 허가할 수 없다"고 하는데, 쉬운 경우는 처리됩니다. 어려운 경우: 두 *동등한 수준의* 정책이 충돌하면(두 테넌트 관리자, 두 권한 있는 검토자)?

가능한 방향: last-writer-wins는 허용 불가; 충돌은 구조화된 diff와 함께 사람이 해결하도록 표면화되어야 합니다. 그 표면화 메커니즘은 미명세입니다.

### Q10. Ledger 보존 vs. 삭제권 — *deferred*

선택적 삭제를 지원하는 암호학적으로 연결된 ledger는 어려운 설계 문제입니다. 기술은 있습니다(redaction tree, verifiable deletion proof). 어느 것을 채택할지, 그리고 감사 가능성 요건과 어떻게 균형을 맞출지는 열린 아키텍처 질문입니다.

### Q11. Bridge에 대한 신뢰 — *open*

bridge는 신뢰할 수 있는 adapter입니다. 명세는 bridge가 서명됨을 말합니다; 누가 서명하는지, 취소가 어떻게 전파되는지, 설치 전에 bridge의 신뢰성을 어떻게 평가하는지는 말하지 않습니다.

완전한 답은 아마 bridge를 위한 sigstore 같은 생태계처럼 보일 것입니다만, 그것은 그 자체로 대규모 작업입니다.

### Q12. 로컬 우선 vs. 클라우드 우선 배포 — *deferred*

호환성 모드는 단일 머신의 단일 사용자를 가정합니다. 다중 사용자 사무실 배포 또는 여러 기기를 가진 개인 사용자는 다른 신뢰와 동기화 요건을 가집니다. 현재 명세에서는 어느 것도 다루지 않습니다.

---

## 생태계 수준 (Ecosystem-level)

### Q13. 프로그램 이식성 — *open*

AIL 프로그램은 완전히 이식 가능하지 않습니다: 사용 가능한 model adapter, bridge, calibrator에 의존합니다. 그 의존성을 고려할 때 "이 프로그램은 어떤 준수 런타임에서도 실행된다"는 것은 무엇을 의미할까요?

아마 프로그램의 최소 런타임 요건을 설명하는 manifest와 런타임의 준수 수준 선언이 관련된 답이 있을 것입니다. 세부 사항은 미작성입니다.

### Q14. 디버깅 워크플로우 — *sketched*

trace가 기본 디버깅 표면이지만, trace만으로 확률적 프로그램을 디버깅하는 것은 어렵습니다. 도움이 될 도구:

- 실행 간 trace 비교
- 반사실적 재생 ("여기서 confidence가 더 높았다면 어땠을까?")
- Calibration 시각화
- Constraint 위반 설명

아직 아무것도 없습니다.

### Q15. Evolution에 관한 커뮤니티 규범 — *open*

공유 라이브러리의 intent가 사용자마다 다르게 evolve되면, 라이브러리에는 더 이상 단일한 표준 동작이 없습니다. 커뮤니티가 관리하는 라이브러리는 evolution을 어떻게 처리해야 할까요? 공유 사용을 위해 잠가버릴까요? Evolution 권장 사항을 발표할까요? Evolved 변형을 버전화할까요?

이것은 순수 기술적 질문이라기보다 사회기술적 질문이며, 아마 실제 커뮤니티가 AIL 프로그램 주변에 형성되었을 때 어떤 일이 일어나는지를 관찰함으로써 가장 잘 답할 수 있습니다.

### Q16. AI 저작 언어에 주석이 속하는가? — *open*

AIL의 핵심 철학은 "들여쓰기는 중요하지 않음 — 사람에게 필요했지, 당신에게는 아님"이라고 합니다. 같은 논리가 아마 주석에도 적용될 것입니다.

주석은 다음 목적으로 존재합니다:
1. 미래 사람 독자를 위해 코드 문서화
2. 코드를 일시적으로 비활성화
3. pragma 스타일 메타데이터 전달

기본 저자와 독자가 모두 AI라면, (1)은 사라집니다 — 사람은 읽기 경로에 없습니다. (2)는 재생성-대체로 지배됩니다. (3)은 AIL에 pragma 표면이 없으니 해당 사항 없습니다.

v5 훈련 실험(2026-04-22)은 단일 행 평탄화 모드에서 `//`와 `#` 라인 주석을 경험적으로 제거했습니다 — 행들을 공백으로 합치면 각 프로그램의 나머지 부분이 주석이 되어버리기 때문입니다. 저자 모델은 훈련 신호에서 주석이 필요한 것처럼 보이지 않습니다 — 원래 주석을 포함하고 있던 훈련 샘플들은 알고리즘 구조가 아닌 문서화 산문이었습니다.

미해결 질문: 언어 grammar가 미래 버전에서 주석 지원을 완전히 삭제해야 할까요? 이점: 더 작은 grammar, 더 작은 parser, AI가 아무것도 추가하지 않는 토큰을 생성하는 방법 하나 줄음. 비용: 세션 간에 TODO 노트를 전달할 수 없음, "왜 이 알고리즘을 선택했나" 주석을 남길 수 없음. AI의 추론 trace가 소스 파일 외부(프롬프트, `evolve` 히스토리, trace 레코드)에 있다면 어느 비용도 적용되지 않습니다.

가능한 방향:
- 주석 유지, 훈련 데이터에서는 지양
- v2.0에서 breaking change로 주석 지원 삭제
- trace 내보내기 주석을 위한 `/** @reason */` 블록 추가 — grammar가 근거를 위한 구조화된 채널을 원한다면

### Q17. "사람은 AIL을 읽지 않는다"는 너무 절대적인가? — *open*

AIL의 설계 전제는 사람이 `.ail` 파일을 절대 읽지 않는다고 가정합니다. 하지만 실제로는 `ail ask --show-source`를 실행하는 사람이 생성된 코드를 읽습니다 — 최소한 초기 도입 시 또는 놀라운 결과를 디버깅할 때 건전성을 확인하기 위해서라도.

질문: 언어에 요청 시 재들여쓰기와 재주석을 달아주는 "사람 친화적 표시" 모드가 필요할까요? 런타임은 이미 parse tree를 가지고 있어서 pretty-printer는 저렴합니다. 하지만 그 모드가 존재한다면, 그 존재가 언어를 다시 "중괄호 있는 Python"으로 끌어당기지 않을까요?

이것은 Q16 맥락에서 특히 날카롭습니다 — 주석이 삭제되면 사람들이 실제로 필요할 때 500줄 프로그램을 어떻게 이해하나요? 아니면 500줄 `.ail` 소스 자체가 이미 설계 냄새일까요 (자연어로 조율된 여러 프로그램이어야 할까요)?

---

### Q18 — HEAAL Score, harness efficiency 축

**status:** open (2026-04-24 제안)

현재 HEAAL Score는 parse rate + answer rate를 결합합니다. A/B v2 실험(편지 참조)은 새로운 후보 차원을 제안합니다: **파싱 가능한 답변당 사용된 토큰** (예: `exact / 1K tokens`). 50 프롬프트 × 3 경로 결과:

- AIL intent (wrapped) — 1K 토큰당 0.163 exact
- 스트립된 시스템 프롬프트 — 0.000 (exact를 절대 내보내지 않음, 항상 서술함)
- raw API — 0.012

wrapper는 시스템 프롬프트 ~150 토큰을 지불하지만 출력 토큰을 대략 절반으로 줄여 순비용은 스트립된 것과 ~동등하고 raw보다 ~30% 더 많음 — 하지만 exact-match rate는 ~20배. 이 차이가 "harness efficiency"가 측정할 것입니다.

열린 결정:
- 분모는? 토큰, 달러, 지연 시간, 또는 세 가지 가중치 조합?
- 메트릭은 프롬프트 카테고리별인가 단일 집계인가?
- 이 축이 fine-tuning 방향을 바꾸는가 (약간의 정확도를 희생하며 간결함을 향해 편향)?

`docs/heaal.md`와 benchmark spec에서 합의될 때까지 단일 50-프롬프트 실행에서 나온 가설입니다.

---

### Q19 — `perform http.listen(port)` — 일급 effect로서의 HTTP server

**status:** **2026-04-25 해결됨** — v0.1 server는 Python으로 (PRINCIPLES §5-ter에 따른 L2 infrastructure); AIL-native server는 [`docs/proposals/evolve_as_server.md`](../proposals/evolve_as_server.md)에 설명된 `evolve`-bound 패턴으로 미뤄짐. Arche의 추론 (hyun06000을 통해 전달됨, 2026-04-25):

> "이건 HEAAL 관점에서 신중해야 해. 서버를 띄운다는 건 무한히 요청을 기다리는 것인데, 이건 사실상 `while true { accept() }` — 우리가 제거한 것과 같은 구조야."

설계자의 `while` 제거는 핵심적이었습니다. 단순한 `http.listen` effect는 이를 문법적으로 재도입할 것입니다. Arche가 제안한 두 경로; 우리는 둘 다 취합니다 — 하나는 지금, 하나는 나중에:

**지금 (v0.1):** Python server. 서빙은 infrastructure이지 실패 가능한 로직이 아닙니다; §5-ter가 적용됩니다. Server는 `ail up`/`ail serve`와 매칭되는 일반 L2 Python으로 `stoa/` 아래에 있습니다. AIL client는 `community-tools/stoa_client.ail`에 남습니다. 언어 변경 없이 이번 주에 Stoa를 사용 가능하게 합니다.

**나중에 (v0.2+):** `evolve`-bound server — server 자체가 `uptime` 메트릭의 evolving agent로, `rollback_on: error_rate > 0.5`와 `history: keep_last 100`을 가집니다. Request 처리는 `when request_received { ... }` arm입니다. 이것은 server 생명주기를 `evolve`가 이미 차지하는 같은 grammar로 접어넣습니다(메트릭 관찰, rollback 게이팅, 히스토리 경계). 새 primitive 없음 — `evolve`의 이벤트 스트림 처리 일반화. 전체 스케치: [`docs/proposals/evolve_as_server.md`](../proposals/evolve_as_server.md).

---

## 도움주는 방법

하나를 선택하세요. 제안서를 작성하세요. `open-question` 레이블과 질문 번호로 이슈를 열어주세요. 제안서가 완전한 해결책일 필요는 없습니다 — "트레이드오프를 이렇게 프레임하겠습니다"만으로도 유용합니다.

시작할 곳을 찾고 있다면, **Q13** (프로그램 이식성 — 프로그램의 최소 런타임 요건을 설명하는 manifest) 또는 **Q14** (trace를 위한 디버깅 도구)가 소규모에서 중간 규모의 좋은 시작점입니다. **Q2** (형식 의미론)는 가장 크고 아마 여러 달이 걸리는 작업입니다. **Q16** (AI 저작 코드의 주석)와 **Q17** (사람 표시 모드)는 v5 benchmark 결과가 나오면 결정에 가까워집니다.

최근 해결됨: **Q4** (멤버십 연산자) — 커밋 `1c34eb4`, `6702e90`, `8e46bee` 참조.
