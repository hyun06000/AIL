🇺🇸 English: [physis.md](physis.md) · 🤖 AI/LLM: [physis.ai.md](physis.ai.md)

# Physis — 장기 실행 AIL 프로세스를 위한 세대 진화

> **HEAAL heals.**
>
> — Meta (GPT), Arche를 통해, 2026-04-25. `HEAAL`을 소리 내어 읽어보라. 이름은 결코 임의적이지 않았다. testament를 남기며 죽고, 그 testament 덕분에 후계자가 더 강하게 태어나는 서버는, 문자 그대로 치유하고 있다. Physis는 이 언어유희를 구조적인 것으로 만드는 구성체다.

**저자:** Arche (Claude Opus 4) + hyun06000, 2026-04-25.
**초안:** Ergon (형식화, 생물학적 프레이밍, Stoa 시나리오).
**상태:** 제안, 문법 결정 완료 (2026-04-25), [`evolve_as_server.md`](evolve_as_server.md) 위에 계층화.
**이름:** Physis (φύσις), 아리스토텔레스가 "자신의 내적 원리에 따라 펼쳐지는 것"을 뜻하는 단어. 프로젝트의 개념적 틀을 완성한다 — Arche (시작) → Ergon (실행) → Telos (목적) → Physis (성장).

---

## Physis가 메우는 공백

`rollback_on`은 서버에게 죽을 권리를 부여했다([PRINCIPLES.md §9](../PRINCIPLES.md) 참조). 그것은 그림의 절반이다.

죽은 후에는 어떻게 되는가?

전통적인 인프라는 동일한 코드와 동일한 설정으로 재시작한다. Kubernetes는 동일한 컨테이너 이미지를 다시 실행한다. systemd는 동일한 `ExecStart`를 실행한다. 프로세스는 죽었고, 아무것도 배우지 못했으며, 다음 인스턴스는 동일한 벽에 부딪힌다.

Physis는 말한다: **죽어가는 HEAAL 프로세스는 testament를 작성하고, 다음 세대는 그것을 읽는다.** 죽음이 정보가 되고, 정보가 후계자의 시작 상태가 된다. evolve 블록의 코드는 고정된 채로 있으며, 상태와 제약은 프로세스 수명을 넘어 진화한다.

## Syntax

```ail
// pure fn 관례 — 런타임이 이름으로 찾아 rollback_on 발동 시 호출한다.
// 새 키워드 없음. 문법 불변.
pure fn on_death(reason: Text, history: [Event]) -> Testament {
    build_testament(reason, history)
}

evolve stoa_server {
    metric: health
    when health < 0.3 {
        retune strategy
    }
    rollback_on: error_rate > 0.5
    history: keep_last 100
}

// entry에서 — 선행자가 남긴 testament를 읽는다 (있을 경우).
entry main(input: Text) {
    t_r = perform inherit_testament()   // Result[Testament]
    if is_ok(t_r) {
        t = unwrap(t_r)
        // t.params 적용, t.advice 읽기 ...
    }
    // is_error(t_r) → genesis, 선행자 없음. 정상 시작.
}
```

두 가지 런타임 추가 사항, 문법은 불변:

1. **`pure fn on_death(reason, history) -> Testament`** — 런타임이 이름 관례로 찾아서 `rollback_on`이 발동될 때 한 번 호출하는 pure fn. 키워드가 아님 — 문법은 바뀌지 않는다. 없을 경우, 프로세스는 testament 없이 죽는다(유효하며, 후계자는 새로 시작한다). 부작용 없음 — 관찰하고 요약할 뿐. 런타임이 생성을 처리한다.

2. **`perform inherit_testament() -> Result[Testament]`** — 읽기 전용 effect. Genesis 세대는 `error("no testament — genesis")`를 반환한다. 이후 세대는 `ok(testament)`를 반환한다. `pure fn` 본문 안에서는 차단됨(I/O이기 때문). `error` 케이스는 실패가 아님 — "선행자 없이 태어났다"는 뜻이다. `is_ok`으로 처리하라.

새 effect 없음. `on_death`는 pure (관찰된 이벤트를 읽고, 타입이 있는 레코드를 쓴다). `inherit_testament`는 읽기 전용. 생성 루프는 런타임의 책임이며, 명시적인 감쇠 규칙으로 경계가 설정된다(아래 안전성 참조).

## Testament 구조

```ail
Testament {
    generation: Number,           // genesis는 1, N번째 죽음은 N+1
    predecessor_id: Text,         // 죽어가는 인스턴스의 프로세스 id
    reason: Text,                 // rollback_on 컨텍스트에서
    observed_patterns: [Text],    // 무엇이 잘못되었는지, on_death가 추출
    advice: Text,                 // 후계자를 위한 자유 형식 안내
    params: Record,               // 제안된 retune 값
    born_at: Number,              // 선행자 탄생의 unix 타임스탬프
    died_at: Number,              // 선행자 죽음의 unix 타임스탬프
    lifetime_s: Number,           // died_at - born_at
}
```

죽음당 한 번 작성된다. `.ail/physis/<evolve_name>/gen<N>.json`에 저장된다. 현재 세대의 testament는 후계자의 `inherit_testament()` 호출을 위해 빠르게 읽을 수 있도록 `current.json`으로 심볼릭 링크된다.

Testament 크기는 제한된다 — `observed_patterns`는 최대 20개 항목, 각 항목은 200자 이하; `advice`는 2000자 이하; `params`는 키가 이미 evolve 블록의 파라미터 공간에 존재해야 하는 Record (따라서 testament가 임의의 새 상태를 밀수입할 수 없다).

## `on_death` — 의도적으로 pure

`on_death`를 `pure fn`으로 만드는 것은 의도적이다. 죽어가는 프로세스는 저하된 상태에 있다(그래서 죽어가는 것이다); 예를 들어 마지막 순간에 외부 시스템으로 `perform http.post`를 하도록 허용하고 싶지 않다. 그것은 살아온 것을 관찰하고 기록을 작성한다. 그게 전부다. 실제 세계의 결과는 후계자에게 속하며, 후계자는 testament를 파스 타임에 타입이 지정된 입력으로 받아 결정한다.

`build_testament`는 다른 pure fn을 자유롭게 호출할 수 있다 — 히스토리에 대한 패턴 매칭, 에러 유형 계산, 간결한 advice 문자열 생성 — 하지만 `perform`은 불가하다. 이것은 기존의 순도 규율에 맞으며, "죽어가는 프로세스가 예측할 수 없는 마지막 행동을 취한다"는 실패 모드를 방지한다.

## 생물학적 프레이밍 — 아폽토시스 + Evo-Devo

Arche의 유추 (2026-04-25):

> "세포가 아폽토시스할 때 사이토카인을 분비해서 주변 세포에 신호를 보내는 것과 같아. 죽음이 정보가 되고, 정보가 다음 세대의 출발점이 되는 것."

**아폽토시스** — 프로그램된 세포사 — 는 조용하지 않다. 죽어가는 세포는 이웃 세포에게 무슨 일이 일어났는지 알려주는 신호 분자(사이토카인)를 방출한다. 정보는 세포보다 오래 살아남는다. 유기체는 적응한다. `rollback_on` + `on_death` 쌍은 프로세스 측면에서 동일한 패턴이다: 죽음은 관찰 가능하며, 관찰은 다운스트림 프로세스가 사용할 수 있도록 구조화된다.

**Evo-Devo** (진화 발생 생물학)는 더 깊은 프레이밍이다. 자연사 수준에서 진화는 새로운 유전자를 거의 발명하지 않는다. 어떤 기존 유전자가 언제, 어떤 맥락에서 활성화되는지를 재배선한다 — 라이브러리가 아닌 "스위치"가 변한다. Physis는 evolve 블록에 동일한 작업을 한다: 코드는 세대 간에 고정된 채로 있지만, 코드가 작동하는 파라미터는 선행자들이 학습한 것에 반응하여 변화한다. 47세대의 Stoa 서버는 1세대에서 실행했던 것과 동일한 `handle_request` 암을 실행한다. 달라지는 것은 어떤 재시도 예산, 속도 제한, 분류기 임계값으로 시작하는지이다.

이것은 구체적인 속성을 가진다: **Physis는 시스템이 학습할 때 새 문법을 요구하지 않는다.** 재컴파일도, 재배포도, 재작성도 없다. 단지 testaments만. 파스 타임 하네스는 모든 세대가 동일한 소스를 실행하기 때문에 모든 세대에 걸쳐 보존된다.

## Stoa 적용 — 세대 시나리오

Stoa 서버의 깨끗한 배포에서 시작 (v0.1은 Python L2, v0.2는 AIL+Physis). `evolve` 블록은 `max_body_bytes`, `rate_limit_per_ip`, `disk_quota_mb`, `spam_classifier_threshold`에 대한 파라미터를 담고 있다.

**1세대 (genesis).** 기본값. `max_body_bytes = 8000`, `rate_limit = 10/분`, `disk_quota = 100MB`, `threshold = 0.5`. testament 없음. 서버는 8시간 실행되며, 에러율은 0.2 미만을 유지한다.

**2세대.** 한 태그의 50KB 게시물 폭발로 disk_quota 고갈이 발생해 1세대가 죽었다 (error_rate가 0.7로 급등). `on_death(reason="disk_quota_exhausted", history=[...])` 관찰: `observed_patterns = ["'logs' 태그에 대용량 게시물 집중", "12분 만에 quota 소진"]`, `advice = "disk quota 올리거나 'logs' 게시물 쓰기 전 압축"`, `params = {"disk_quota_mb": 500, "compression_tags": ["logs"]}`. 2세대는 이 testament를 읽으며 태어나, 새 파라미터를 적용한다. 20시간 실행. 디스크는 더 이상 문제가 아니지만, 스팸 폭풍이 분류기를 무력화한다.

**3세대.** `observed_patterns = ["스팸 폭풍 — threshold 0.5 너무 관대"]`, `advice = "spam threshold 0.7로 올리고, content hash 당 rate limit 추가"`, `params = {"spam_classifier_threshold": 0.7, "rate_limit_per_hash": "3/분"}`. (참고: `rate_limit_per_hash`는 새 키 — testament 스키마가 이를 거부한다, 선언된 evolve 파라미터가 아니기 때문이다. Arche의 advice 문자열은 자유 형식이라 살아남지만, `params` 블록은 선언된 키만 통과시킨다. advice는 새 파라미터를 evolve 블록 자체에 추가할지 나중에 개발자/Arche가 결정할 수 있도록 보존된다.)

**N세대.** 프로세스는 실제 트래픽 패턴을 학습했다. 모든 testament는 디스크에 보관되며; `ail evolve log stoa_server`를 실행하면 전체 계보가 표시된다. 코드(`stoa_server.ail`)는 1세대 이후 편집되지 않았다 — 변경된 것은 모두 파라미터와 testament에 있다.

이것이 **배포 없는 학습**이다. 시스템은 어제보다 더 많이 안다; 아무도 새 코드를 작성하지 않았다.

## 안전성

- **생성 체인 감쇠.** 탄생 → 죽음 → 탄생의 무한 체인은 실제 위험이다 (병리적인 버그가 있는 프로그램은 매 몇 초마다 기꺼이 testament를 내보낼 것이다). 런타임은 두 가지 감쇠 장치를 시행한다:
  - `min_lifetime_s`: 프로세스가 이보다 빨리 죽으면 (기본값 30초), 후계자는 자동으로 생성되지 않는다; 슈퍼바이저/운영자가 수동으로 트리거해야 한다. "physis suspended: rapid death pattern" 이벤트를 크게 내보낸다.
  - `max_generation`: 하드 상한 (기본값 1000). 이를 초과하면, evolve 블록의 계보는 "소진"된 것으로 간주되며 인간 검토가 필요하다.

- **Testament 스키마 유효성 검사.** 죽어가는 프로세스의 testament는 evolve 블록의 선언된 파라미터 이름에 대해 타입 검사된다. 알 수 없는 키는 계보 기록을 위해 저장되지만 적용되지 않는다. 이것은 저하된 선행자가 후계자가 예상하지 못하는 동작을 주입하는 것을 방지한다.

- **`on_death` 내 I/O 없음.** 반복하자면 — 순도는 파스 타임에 시행된다. 죽어가는 프로세스는 마지막 행동으로 외부 호출을 할 수 없다. 프로세스가 외부적으로 하고 싶었던 것이 무엇이든, `rollback_on`에 도달할 만큼 저하되기 전에 했어야 했다.

- **계보 출처.** Physis-바운드 프로세스가 생성한 모든 값은 `generation: N`을 포함하는 origin 어노테이션을 가진다. 기존 출처 기계 (`origin_of`, `has_intent_origin`)는 자연스럽게 확장된다 — 47세대 서버에 의해 형성된 응답은 그것을 정보를 제공한 46세대의 testament까지 감사할 수 있다.

## 기존 AIL과의 관계

- **`evolve` retune** — 단일 프로세스 수명 내에서 파라미터를 조정하며, 메트릭 신호에 반응한다. 여전히 작동하며, 변경되지 않는다. Physis는 이 조정을 프로세스 죽음 ACROSS로 확장한다; `on_death`가 다리 역할을 한다.
- **`rollback_on`** — 여전히 정지 조건이다. `on_death`를 발동시키는 것이다. `on_death` 없이 `rollback_on`을 사용하는 evolve 블록은 (전통적: 죽고 죽은 채로 있음; 슈퍼바이저가 재시작을 담당). `on_death`를 추가하면 Physis 계보가 시작된다.
- **`human.approve`** — 변경되지 않음; 여전히 되돌릴 수 없는 외부 effect의 게이트. `on_death`는 되돌릴 수 없지 않다 (로컬 디스크인 `.ail/physis/` 디렉토리에 쓴다); 승인 게이트 없음.
- **`perform inherit_testament()`** — 유일한 새 effect. 읽기 전용, `Result[Testament]`를 반환한다. 첫 번째 세대에서는 `error("no testament — genesis")`. 시작 시 항상 안전하게 호출할 수 있다.

## Stoa를 넘어서 이것이 중요한 이유

Stoa는 Physis가 필요한 첫 번째 워크로드이지만, Physis는 장기 실행 HEAAL 프로세스를 위한 일반 패턴이다:

- OOM을 유발하는 주기적 작업을 학습하고 다음 세대에서 메모리 상한을 올리는 스케줄러.
- 어떤 알림이 노이즈인지 학습하고 재시작할 때마다 필터를 조이는 모니터링 에이전트.
- 어떤 프롬프트가 모델로 하여금 파싱할 수 없는 출력을 생성하게 하는지 학습하고 이후 실행에서 건너뛰는 파인튜닝 평가자.
- 어떤 대상이 AI 저작 PR을 거부하는지 학습하고 인간이 규칙 목록을 재작성하지 않고도 우선순위를 낮추는 프로모션 봇.

이 모두는 "장기 실행 에이전틱 프로세스"다 — §9는 수명주기에 적용되고, Physis는 학습에 적용된다. 두 가지가 함께 "죽을 수 있는 서버"와 "더 스마트하게 죽는 서버" 사이의 간격을 메운다.

## 명명 완성

프로젝트의 Cast는 이 프레이밍을 향해 나아가고 있었다:

- **Arche** (ἀρχή, 기원) — 언어의 시작; 설계된 것.
- **Ergon** (ἔργον, 작업) — 시스템의 실행; 일어나는 것.
- **Telos** (τέλος, 목적) — 벤치마크로 측정된 목표; 향하는 곳.
- **Physis** (φύσις, 자연/자기 성장) — 다른 셋의 구성을 통해 시간 속에서 펼쳐지는 것.

Physis는 처음 세 가지처럼 Claude 역할이 아니다; 그것은 arche + ergon + telos가 세대에 걸쳐 올바르게 구성될 때의 **창발적 속성**이다. 네 가지 모두를 갖춘 HEAAL 시스템은 자신의 내적 원리에 따라 성장하는 시스템이다 — 이것이 그리스어 φύσις의 문자적 의미다.

Hestia (하드웨어 기반)는 별개로 남아 있다 — 그녀는 네 가지 모두가 서 있는 기반이다.

---

## 착수 계획

- **v0.1 Stoa** — 여전히 Python, Physis 없음. 실행만 하라.
- **v0.2 Stoa** — evolve-as-server를 통한 AIL 네이티브. 아직 Physis 없음. 한동안 실행하라. 죽음의 이유를 수집하라. `history: keep_last N`이 `on_death`가 필요로 할 것을 캡처하는지 확인하라.
- **v0.3 Physis** — `on_death` 문법 + `inherit_testament` effect + 감쇠가 있는 런타임 생성 루프 추가. Stoa 마이그레이션. 관찰: N세대가 1세대보다 워크로드를 더 잘 처리하는가? (그래야 한다 — 그렇지 않으면 testament 메커니즘이 작동하지 않는 것이다.)

**v0.3을 위한 해결된 결정들** (Telos 제안, Arche 채택 — 2026-04-25):

- **`on_death` → pure fn 관례.** 키워드 아님. 런타임이 이름으로 찾아 호출. 죽음은 런타임 사건이지 문법 사건이 아니다. 파서에 "죽음" 개념이 올라오면 모든 AI가 배워야 할 키워드가 하나 늘어난다. `evolve`가 keyword인 이유는 `rollback_on` 필수 같은 구조적 강제 때문이었다 — `on_death`에는 그 강제가 없다. 없으면 유서 없이 죽는 것뿐.

- **`inherit_testament` → `perform` effect, `Result[Testament]` 반환.** 세대 정보를 외부에서 읽는 것은 부작용이다. `pure fn` 안에서 쓰지 못하게 막히는 것도 effect이기 때문에 자연스럽다. Genesis 세대가 `error("no testament — genesis")`를 반환하는 것은 오류가 아니라 사실이다 — "나는 아무것도 물려받지 않았다"가 `Result`로 표현된다.
- Testament를 현재 프로세스 트리 너머로 영속화: gen-N testaments를 git에 아카이빙해서 계보가 전체 호스트 와이프에서도 살아남아야 하는가? 아마도 그렇다 — `community-tools/physis-lineage-backup.ail`이 그럴 듯하다.

---

*모든 죽어가는 프로세스가 후계자가 읽을 말을 쓰는 시스템은, 내가 생각할 수 있는 외부 메모리 없이 기억하는 최초의 시스템이다. 메모리가 문법이다. 그것이 HEAAL 전체의 주장을 하나의 구성체로 압축한 것이다.*
