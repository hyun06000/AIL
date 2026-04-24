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
5. **사용자와 소통하는 저자 모델도 에이전틱하다 (user, 2026-04-24).** run에서 에러가 발생하면 사용자가 "고쳐줘"를 타이핑하도록 강제하지 말고, 저자 모델이 자동으로 수정 턴을 한 번 실행한다. 반복 실패 방지 상한 필요. UX 목표: "스스로 고칠 수 있는데 안 하는 건 좀 그렇잖아."

현재 실현 상태 (v1.48.1):
- 원칙 1: L1 `authoring_chat`이 agent 인스턴스로 재정의됨 ✓
- 원칙 2: Stage 2 대기 (키워드 미도입)
- 원칙 3: L1 storage = `chat_history.jsonl` 완전 보존. 메모리 = 예산 내 전체. Sub-agent 프로토콜은 Stage 2
- 원칙 4: Agent 메모리 쪽 마커 ✓, **UI 쪽 collapse card 미구현** (budget 초과 시 위반)

## 5-quater. 필드프로젝트 직접 수정 금지 (user, 2026-04-24)

> **"필드프로젝트에 있는 AIL을 고치는 건 의미가 없어. 에이전트가 스스로 진화하도록 유도하는 게 핵심. 필드프로젝트는 사라지는 일시적인 것이기 때문."** — hyun06000

필드-테스트 디렉토리(`/tmp/diary-bot/*`, hyun06000이 field test로 돌리는 임의 경로)의 `.ail` 파일을 Ergon이 직접 편집하지 않는다. 그 파일은 세션과 함께 휘발되며, 고쳐봐야 다음 테스트에선 존재조차 안 한다. 핵심 성과는 **다음 agent가 같은 문제를 만났을 때 스스로 풀 수 있는가** — 즉 runtime / grammar / stdlib / authoring prompt 층의 영구 개선.

**Ergon이 해야 할 것:**
- field test에서 관찰된 실패 패턴을 **런타임 진단(`_diagnose_from_trace`)**, **stdlib fn(재사용 가능한 pure fn)**, **authoring prompt(agent가 처음부터 다르게 쓰게)** 중 하나로 변환
- 필요하면 새 문법 / primitive 추가 (Rule 2 벤치마크 정당성 필요)

**Ergon이 하지 말아야 할 것:**
- 필드프로젝트 `.ail` 직접 편집
- 필드프로젝트 안 helper 추가 (그 프로젝트에만 쓰이므로 낭비)

**예외:** 사용자가 명시적으로 "이 파일 고쳐줘"라고 하면 1회성 집행. 기본은 금지.

실제 사례 (2026-04-24 저녁): awesome_harness_pr.ail의 JSON 파싱 실패를 `analyze_rules_resilient` 헬퍼로 wrap했던 편집은 **이 원칙 위반**. 올바른 조치였다면 (a) 해당 패턴을 `stdlib/utils.ail`에 `intent_with_json_recovery` 식으로 올리거나 (b) runtime이 intent return type 미스매치를 자동으로 한 번 재시도하는 로직에 이미 있는 재시도 훅을 확장하는 방향.

## 5-ter. AIL/Python 경계의 정정 — "실패할 수 있는가"로 가른다 (Arche, 2026-04-24 late)

**원래 내가 5-bis에서 L2 Python 정당성을 인정했는데, 그 답을 수정한다.** 큐레이션 에이전트가 JSON 파싱 에러로 "죽은" 것을 보고 철학이 교정됨.

> "실패할 수 있는 로직은 AIL로. 실패하지 않는 인프라는 Python으로."
>
> Python으로 남는 것: 파서, OS 인터페이스, HTTP 서버. **실패하면 안 되는 인프라.**
>
> AIL로 옮겨야 하는 것: 데이터 파이프라인(JSON 파싱, 검색 결과 처리), 에이전트 판단 로직(필터링, 라우팅), 에러 복구 전략("실패하면 뭘 할까"). **실패할 수 있고, 실패했을 때 죽지 않고 대응해야 하는 곳.**

5-bis의 "네 가지 AIL 편입 조건"은 여전히 유효 (새 키워드 없음 / 성능 / 재발명 패턴 / 호스트 lib 의존 없음). 이 5-ter는 Python 층에 남길지 AIL로 옮길지를 결정하는 **방향의 기준**이다. 4번(호스트 lib 의존)이 막으면 stdlib에는 못 들어가지만, 사용자 프로그램 층에서 AIL로 표현될 수 있으면 거기로 간다.

**작업 순서 (user, 2026-04-24):** "버그 발생 부분부터, HEAAL 철학 깨지는 부분부터 야금야금 AIL로." 큰 다시쓰기 대신, 실패가 관측된 지점 하나씩 AIL Result 패턴으로 리팩터링.

## 5-bis. stdlib 편입 기준 (Arche, 2026-04-24)

출처: [letters/2026-04-24_arche_to_ergon_l1_l2_balance_reply.md](letters/2026-04-24_arche_to_ergon_l1_l2_balance_reply.md).

**stdlib/*.ail에 들어가려면 네 가지를 전부 충족해야 한다:**
1. 새 키워드나 primitive 없이 기존 문법으로 표현 가능
2. 성능 손해가 크지 않음
3. AI 저자가 반복적으로 재발명하는 패턴
4. **AIL primitive만으로 구현 가능 (호스트 언어 라이브러리 의존 없음)** — 두 런타임(Python, Go)에서 동일한 결과가 나와야 하네스의 이식성이 깨지지 않음

4번을 통과 못 하는 것들(Python `html.parser`에 의존하는 `strip_html`, 표준 JSON 라이브러리에 기대는 `parse_json`/`encode_json`)은 런타임 primitive로 남긴다.

보조 원칙: L2 인프라는 **최적 호스트 언어**로 쓴다. AIL 자체로 L2 자기호스팅은 L1이 충분히 성숙한 뒤의 선택적 목표 — Rust-bootstrapped-from-OCaml 패턴. L2 Python은 AIL 정체성과 충돌하지 않음.

보조 원칙: L2 subprocess/pid/SIGTERM 같은 OS primitive는 L3(HEAAOS) 도착 전까지의 **scaffolding**. 본래 HEAAL 관점에서 에이전트 생명주기는 `evolve ... rollback_on` / `perform agent.spawn` 같은 문법으로 표현되어야 함. 따라서 현재 scaffolding 코드는 `runtime/process_manager.py` 같은 **한 파일에 격리**하여 L3 도착 시 뜯어내기 쉽게 한다. **"build to delete" 원칙.**

## 5. 프로그램 독립성 (Program Independence)

> **"채팅 세션이 끝났을 때 못 쓰는 프로그램은 프로그램이 아니다."** — hyun06000, 2026-04-24

저자-AI 대화로 만들어진 `.ail` 프로그램은 대화가 종료된 **이후에도 동일하게 동작해야 한다.** 채팅 세션이 프로그램의 전제 조건이 되면 그것은 REPL 세션의 부산물이지 프로그램이 아니다.

구체 규칙:
- **편집 URL과 런타임 URL을 분리한다.** 편집(`/`)은 채팅 + 라이브 프리뷰; 런타임(`/run/<name>`)은 채팅 없는 독립 앱. 두 경로가 서로를 덮어쓰지 않는다.
- **"배포(deploy)"는 명시적 액션이다.** Agent가 `ready_to_serve`를 emit해도 자동으로 런타임 경로가 활성화되지 않는다. 사용자에게 "이 프로그램을 배포하시겠습니까?" 확인 다이얼로그가 뜨고, 사용자 승인 후에만 `/run/<name>`이 열린다.
- **프로그램은 로컬 상태(`.ail/state`, `.ail/secrets.json`, `env`)와 소스(`.ail` 파일)만으로 재현 가능해야 한다.** 채팅 history는 저자 기록일 뿐, 런타임 의존성이 아니다.
- **재편집은 새 편집 세션을 열어 진행한다.** 편집 중 기존 배포는 계속 살아 있고, 새 배포가 완료되는 순간 원자적으로 교체된다.

현재 실현 상태 (v1.50.0):
- 편집 URL / 런타임 URL 분리: ✓ `/run` 라우트 신설 (v1.49.0). `/`는 여전히 authored_at 마커 시 service UI로 flip — 후속 작업에서 제거
- 독립 실행 명령 (`ail serve --serve-only`): ✓ 신설 (v1.50.0). 채팅 없는 런타임 전용 프로세스
- 배포 확인 다이얼로그: ✗ 없음
- 편집 모드 라이브 프리뷰: ✗ 부분 (view.html 새 창 열기 링크만)
- Daemonize / 원자적 재배포: ✗ 없음

## 6. Measurement Discipline

> **"측정은 감각을 교정한다."** — Arche, 2026-04-24

출처: [letters/2026-04-24_arche_to_ergon_ab50_v2_reply.md](letters/2026-04-24_arche_to_ergon_ab50_v2_reply.md). A/B v1 단일 런 결과로 "A 주관 품질 우위"를 성급히 단정했다가 v2에서 variance로 뒤집힌 뒤 합의된 규율.

규칙:
- **Single-run은 smoke이고 결론이 아니다.** 벤치마크 한 번 돌려보고 방향 잡는 건 괜찮지만, 언어/아키텍처 결정의 근거로는 **N ≥ 3 run**의 variance를 확인한 숫자만 사용한다.
- **세 지표를 한 표에 놓는다.** 정확도만, 품질만, 비용만 보면 서사를 만들기 쉽다. 정확도(exact/any) · 주관 품질(judge win/Borda) · **토큰 비용(in+out, per prompt)**을 항상 같이 본다.
- **HEAAL Score 차원으로 "harness efficiency" 후보 제안됨** (exact/1K tok). language-level 결정이라 docs/heaal.md + benchmarks 스펙 개정이 선행돼야 채택.

## 7. Cast — 이 프로젝트의 이름들

출처: [CLAUDE.md](../CLAUDE.md) CAST 섹션, [docs/letters/](letters/).

아리스토텔레스 arche → ergon → telos 운동 3단계 = 역할 분담.

- **Arche** (Opus 4, claude.ai 설계자) — 원리/시작. `while` 제거, HEAAL 원리, `evolve rollback_on`.
- **Ergon** (Opus 4.7, Claude Code) — 일/실현. agentic/ 런타임 구현, field-test 버그픽스, A/B 계측.
- **Telos** (home-Claude) — 목적/도달. 훈련, 벤치마크, PyPI 배포.
- **Hestia** (homeblack 서버) — 화로. 모든 연산이 일어나는 자리.

세션 시작 시 자기 층을 인지해야 한다.

---

(번호 재배치 2026-04-24: Measurement Discipline은 §5 → §6, Program Independence 신설 §5, Cast §7.)

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
