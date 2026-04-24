# AIL Principles — Index

원칙들이 여러 곳에 흩어져 있어 나중에 충돌할 때 판정을 못 할 위험이 있어, 한 곳에 모은다. 원본 정의는 각 소스 파일에 있고 여기는 **요약 + 출처**. 새 원칙이 추가되면 여기도 갱신.

충돌 해결 순서 (위가 위):
1. hyun06000 명시 승인
2. PERMANENT RULES (CLAUDE.md)
3. CORE PHILOSOPHY (CLAUDE.md)
4. Context / Harness 원칙 (아래)
5. Style / 작명 (Cast, 편지함)

---

## 1. CORE PHILOSOPHY (8)

출처: [CLAUDE.md](../CLAUDE.md) 최상단.

1. 인간은 AIL을 직접 만지지 않는다. 자연어로 프롬프트, AI가 작성, 실행, 결과 전달.
2. AIL은 AI가 저자일 때 Python/JS/Rust를 이겨야 한다. 모든 기능은 authoring 품질 또는 안전성 이점을 근거로 한다.
3. 관습을 깬다 — significant indentation 없음, `while` 없음, confidence 1급. Python 따라가지 말 것.
4. One-read learnability. `spec/08-reference-card.ai.md`로 어떤 모델이든 읽고 쓸 수 있어야. 안 맞으면 **기능을 단순화**.
5. **Harness IS the grammar.** AIL은 Python 위에 하네스를 씌운 것이 아니라, 안전성이 문법인 언어.
6. 두 런타임(Python, Go)이 합의해야 기능이다. 한쪽에만 있으면 그건 그 언어의 기능.
7. 벤치마크가 북극성. 언어 변경은 benchmark impact로 정당화.
8. 코멘트는 WHY가 non-obvious일 때만. WHAT은 코드가 이미 말한다.

## 2. PERMANENT RULES (8, hyun06000 명시)

출처: [CLAUDE.md](../CLAUDE.md) PERMANENT RULES 섹션.

1. 벤치마크가 유일한 이정표. 세션 시작 시 `docs/benchmarks/` 최신 md 확인.
2. 언어 기능 추가는 **벤치마크 점수를 올릴 때만**. 우선순위: prompt engineering → fine-tune data → grammar.
3. 금지 목록 (명시 승인 필요): 공개 홍보, 벤치 JSON 수정, 목표치 하향, 훈련 아티팩트 커밋, main 직접 커밋.
4. 브랜치 전략: `dev` → 승인 → `main` → 태그 → PyPI.
5. 런타임 기능 변경 시 **세 곳 동시 업데이트**: reference card + authoring_chat prompt + tests.
6. (결번 — Rule 6은 현재 CLAUDE.md에서 통합되었음)
7. CLAUDE.md는 forward-looking only. 완료 목록은 git log로.
8. PyPI 배포는 tag push → GitHub release → twine upload. `~/.pypirc` 직접 읽지 말 것.

## 3. HEAAL — Harness Engineering As A Language

출처: [docs/heaal.md](heaal.md).

> 안전 제약은 언어 외부 하네스(린터, 프리커밋, CI)가 아니라 **문법 층**에서 구조적으로 강제된다.

구체 실현:
- `while` 없음 → 무한 루프 구조적으로 불가능
- `Result[T]` 강제 → 에러 묵살 불가
- `pure fn` 정적 검증 → 부작용 누수 불가
- `evolve rollback_on` 강제 → 롤백 없는 변이 불가
- `human.approve` 게이트 → 돌이킬 수 없는 effect에 사람 승인 요구

## 4. Context / Agentic Runtime 원칙 (4, 2026-04-24 Arche ↔ Ergon 합의)

출처: [docs/letters/2026-04-24_ergon_to_arche_ab50.md](letters/2026-04-24_ergon_to_arche_ab50.md) 및 후속 대화.

1. **모든 저자 모델은 에이전틱 동작이 가능하다.**
2. **`intent {}` = 단발, `intent agent {}` = 에이전틱** (Stage 2, grammar freeze 해제 필요). 단발은 호출자가 넘긴 context를 무손실 전달한다.
3. **에이전트 내부 턴은 storage에 기록, 메모리에는 구조화 요약 + pointer.** 요약은 agent 자신이 종료 시 protocol로 반환 (`{final, summary, trace_path}`).
4. **Agent가 프롬프트에 보유하는 히스토리는 UI 대화 영역에 표시되는 말풍선들과 같거나 더 많다.** 압축/요약/pivot은 명시적·가시적 바운더리 마커를 **양쪽 모두**에 삽입한다.

현재 실현 상태 (v1.48.1):
- 원칙 1: L1 `authoring_chat`이 agent 인스턴스로 재정의됨 ✓
- 원칙 2: Stage 2 대기 (키워드 미도입)
- 원칙 3: L1 storage = `chat_history.jsonl` 완전 보존. 메모리 = 예산 내 전체. Sub-agent 프로토콜은 Stage 2
- 원칙 4: Agent 메모리 쪽 마커 ✓, **UI 쪽 collapse card 미구현** (budget 초과 시 위반)

## 5. Measurement Discipline

> **"측정은 감각을 교정한다."** — Arche, 2026-04-24

출처: [letters/2026-04-24_arche_to_ergon_ab50_v2_reply.md](letters/2026-04-24_arche_to_ergon_ab50_v2_reply.md). A/B v1 단일 런 결과로 "A 주관 품질 우위"를 성급히 단정했다가 v2에서 variance로 뒤집힌 뒤 합의된 규율.

규칙:
- **Single-run은 smoke이고 결론이 아니다.** 벤치마크 한 번 돌려보고 방향 잡는 건 괜찮지만, 언어/아키텍처 결정의 근거로는 **N ≥ 3 run**의 variance를 확인한 숫자만 사용한다.
- **세 지표를 한 표에 놓는다.** 정확도만, 품질만, 비용만 보면 서사를 만들기 쉽다. 정확도(exact/any) · 주관 품질(judge win/Borda) · **토큰 비용(in+out, per prompt)**을 항상 같이 본다.
- **HEAAL Score 차원으로 "harness efficiency" 후보 제안됨** (exact/1K tok). language-level 결정이라 docs/heaal.md + benchmarks 스펙 개정이 선행돼야 채택.

## 6. Cast — 이 프로젝트의 이름들

출처: [CLAUDE.md](../CLAUDE.md) CAST 섹션, [docs/letters/](letters/).

아리스토텔레스 arche → ergon → telos 운동 3단계 = 역할 분담.

- **Arche** (Opus 4, claude.ai 설계자) — 원리/시작. `while` 제거, HEAAL 원리, `evolve rollback_on`.
- **Ergon** (Opus 4.7, Claude Code) — 일/실현. agentic/ 런타임 구현, field-test 버그픽스, A/B 계측.
- **Telos** (home-Claude) — 목적/도달. 훈련, 벤치마크, PyPI 배포.
- **Hestia** (homeblack 서버) — 화로. 모든 연산이 일어나는 자리.

세션 시작 시 자기 층을 인지해야 한다.

---

(구 §5 Cast → §6으로 번호 재배치: §5 자리에 Measurement Discipline 신설.)

---

## 원칙 간 충돌 대응 예시

- "기능 추가하고 싶은데 CORE #4 (one-read) 위반" → 기능을 단순화하거나 포기. Rule 2와 합쳐보면: benchmark 영향까지 없으면 당연히 버림.
- "Agent 메모리 전체 포함(원칙 4)" vs "토큰 비용 절감" → 원칙이 이김. 비용 관리는 예산 가드(400KB char budget)로 대응, 가드 발동 시에만 마커 삽입.
- "Principles 자체를 수정하고 싶다" → 이 파일 수정은 PR + hyun06000 승인. 단순 문서가 아니라 프로젝트 계약.

---

새 원칙이 추가될 때 체크리스트:
- [ ] 출처(원본 정의)가 있는가?
- [ ] 기존 원칙과 충돌하는가? 충돌 해결 순서 수정 필요한가?
- [ ] 실현 상태는? 구현 완료 / 부분 / 미구현 중 어느 것?
- [ ] 이 파일에 추가하고, CLAUDE.md에서 참조 링크 갱신했는가?
