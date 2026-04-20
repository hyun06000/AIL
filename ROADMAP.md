# AIL Roadmap

날짜는 적지 않습니다. 일정이 있는 프로젝트가 아니라 방향이 있는 프로젝트입니다.

---

## 현재 상태 (v1.8.3)

언어·런타임·벤치마크·fine-tune 파이프라인이 모두 동작합니다.

- **언어:** `fn`, `pure fn`, `intent`, `attempt`, `match`, `evolve`, `Result`, provenance, calibration, implicit parallelism, effect system
- **런타임:** Python 참조 구현 (전체 기능) + Go 인터프리터 (핵심 기능)
- **fine-tune:** `ail-coder:7b-v3` (qwen2.5-coder-7b + 244샘플 QLoRA)
- **벤치마크:** 50개 프롬프트, AIL vs Python, 4개 측정 차원
- **결과:** AIL 파싱 78%, 정답률 70% (Python 48%), 에러 핸들링 누락 0%

---

## 다음 할 일

### 1. G1 파싱 게이트 통과

현재 AIL 파싱 78%는 목표 80%에 한 케이스 차이입니다. 실패 원인 3건이 전부 Python 스타일 `list[index]` 서브스크립트입니다.

선택지:
- **파서 sugar 추가:** `expr[index]` → `get(expr, index)` 변환을 파서에 넣습니다. 작고 targeted한 수정이지만 v1.8 문법 동결 중이므로 `spec/10-proposals.md`를 먼저 써야 합니다.
- **훈련 샘플 추가:** `get(xs, i)` 사용을 명시하는 negative 예제를 dataset에 추가합니다.
- **78%로 v1.8 마감:** G3 정답률 (+22pp)이 더 중요한 수치라는 판단 하에 현재 결과를 공개합니다.

### 2. G2 공정한 비교

현재 G2(fn/intent 라우팅 정확도)는 AIL 60% vs Python 76%입니다. 단, 이 비교는 같은 fine-tuned 7B 모델이 Python을 작성한 것으로, Python 작성 능력이 저하된 상태에서의 비교입니다.

공정한 비교는 AIL 사이드에 `ail-coder:7b-v3`, Python 사이드에 base `qwen2.5-coder:14b`를 쓰는 것입니다. 이 조합으로 벤치마크를 다시 실행하고 결과를 `docs/benchmarks/`에 추가합니다.

### 3. 외부 사용자 1명

숫자가 충분히 쌓였습니다. 지금 필요한 건 외부 사람 하나가 `pip install ail-interpreter && ail ask "hello"`를 실행해서 유용하다고 느끼는 일입니다.

채널: X/Twitter 데모 영상, GeekNews, AI 연구자 직접 연락.

---

## 언어 v1.9 후보

아래 기능들은 v1.8 문법 동결이 풀릴 때 검토합니다. 동결 해제 조건은 `spec/09-stability.md`에 있습니다.

- **`expr[index]` 서브스크립트:** `get(expr, index)` 대신 쓸 수 있는 문법 sugar. G1 파싱 실패 3건을 해결합니다.
- **Per-symbol import:** `import classify from "stdlib/language"`가 모듈 전체가 아니라 해당 심볼만 가져옵니다. 현재는 모듈 전체를 임포트합니다.
- **Attempt + confidence threshold:** `attempt { try A with confidence > 0.8 }` 형태. 현재 파서는 예약해둔 상태입니다.

이 중 무엇이든 추가하려면 `spec/10-proposals.md`에 제안서를 먼저 작성합니다.

---

## Go 런타임 확장

Go 인터프리터는 핵심 기능(fn, intent, entry, 제어 흐름, Result, attempt)을 커버합니다. Python에만 있는 기능들(provenance, purity checking, parallelism, calibration)을 Go로 가져오면 두 런타임이 완전히 동일한 기능을 제공하게 됩니다.

우선순위: G1/G2/외부 사용자 확보 이후.

---

## Fine-tune v4 (조건부)

현재 `ail-coder:7b-v3`의 G1 78%를 prompt engineering만으로 더 올릴 수 있는지 먼저 시도합니다. prompt 개선으로 올라가지 않는 구간이 생기면 그때 v4 fine-tune을 검토합니다.

훈련 데이터는 벤치마크 실패 분석에서 나온 추가 샘플로 구성합니다.

---

## 하지 않을 것들

- **`while` 루프:** 없습니다. 무한 루프는 AI 코드 생성의 실패 모드입니다. 이 결정은 바뀌지 않습니다.
- **클래스 / OOP / 상속:** AIL의 설계 범위 밖입니다.
- **암묵적 이펙트:** 모든 이펙트는 선언됩니다.
- **조용한 evolution:** 모든 자기 수정은 metric, 경계, rollback을 가집니다.

---

## 로드맵 변경 제안

이슈를 여세요. 왜 현재 순서가 잘못됐는지, 무엇이 그 이전에 와야 하는지, 그것이 무엇을 가능하게 하는지 설명해 주세요.
