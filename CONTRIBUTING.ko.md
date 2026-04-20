# AIL에 기여하기

AIL은 초기 단계 언어 프로젝트입니다. 지금 시점에서 설계 비판은 코드만큼, 아니 그보다 가치 있습니다. 풀 리퀘스트를 올리지 않아도 의미 있는 기여가 가능합니다.

---

## 기여하는 방법

### 설계에 반박하기

`spec/`, `runtime/`, `os/` 아래의 명세 문서들은 규범적이지만 최종적이지 않습니다. 어떤 설계 결정이 틀려 보인다면 `design-critique` 라벨로 이슈를 열고 이유를 설명해 주세요. 주저하지 않아도 됩니다. 핵심 결정들이 스트레스 테스트를 거칠수록 프로젝트는 강해집니다.

특히 값진 비판: [spec/03-confidence.md](spec/03-confidence.md)의 confidence 모델, [spec/04-evolution.md](spec/04-evolution.md)의 evolution 경계, [spec/01-language.md](spec/01-language.md)의 purity 규칙.

### 미해결 질문에 답하기

[docs/open-questions.md](docs/open-questions.md)에 프로젝트가 인지하고 있지만 아직 풀지 못한 문제들이 있습니다. 그중 하나를 골라 제안 답변을 쓰는 것, GitHub 이슈로만이라도, 프로젝트를 앞으로 밀어줍니다.

### 예제 프로그램 작성하기

예제가 많을수록 언어를 이해하기 쉬워집니다. 빠진 기능, 혼란스러운 문법 선택, 파서 버그를 드러내는 프로그램을 작성했다면 보내주세요. 예제는 `reference-impl/examples/`에 있습니다.

### 참조 구현 개선하기

파서의 에러 메시지가 간결합니다. 실행기가 모든 제약을 검사하지 않습니다. Confidence 전파는 아직 명목상입니다. 이런 빈틈을 닫는 PR을 환영합니다.

### 런타임 포팅하기

메인 인터프리터는 Python입니다. AIRT의 Rust나 Go 구현이라면 부분적인 것이라도 큰 기여입니다. 성능 베이스라인으로서, 그리고 명세가 구현 가능함을 독립적으로 검증하는 역할로서.

---

## 개발 환경 설정

```bash
git clone https://github.com/hyun06000/AIL.git
cd AIL/reference-impl
pip install -e ".[dev]"
pytest
```

프로그램 실행:

```bash
ail run examples/hello.ail --input "World" --mock --trace
```

---

## 저장소 구조

```
ail-project/
├── spec/              # 언어 명세
├── runtime/           # AIRT 런타임 설계 문서
├── os/                # NOOS 운영체제 설계 문서
├── reference-impl/    # Python 인터프리터
│   ├── ail/           # 소스
│   ├── examples/      # .ail 예제 프로그램
│   └── tests/         # pytest 테스트
└── docs/              # 튜토리얼, FAQ, 미해결 질문
```

---

## 스타일

**명세 문서:** 짧은 문장. 규범적 진술은 MUST/SHOULD/MAY. 교차 참조를 위해 번호 있는 섹션 선호. "블로그 포스트"보다 "RFC" 톤 — 간결하고 정확하게.

**Python 코드:** PEP 8, 타입 힌트 권장. 인터프리터는 영리함보다 명료함을 우선합니다.

**커밋 메시지:** 요약 줄은 명령형, 72자 미만. 본문은 변경 이유를 씁니다. 무엇을 바꿨는지는 diff가 보여줍니다.

---

## 이슈 라벨

- `[design]` — 명세 선택에 대한 질문 또는 비판
- `[bug]` — 참조 구현 동작이 명세에서 벗어남
- `[feature]` — 새 언어 기능 또는 런타임 역량
- `[docs]` — 명세나 문서의 명료화 또는 수정

---

## 행동 강령

직접적이고, 친절하고, 구체적으로. 사람이 아니라 아이디어를 비판하세요. 선의를 가정하세요. 누군가의 추론에 동의하지 않는다면 그들이 놓친 것을 말하세요. 묵살하지 말고.

한국어로 이슈·PR을 여셔도 됩니다.

---

## 라이선스

기여하시면 기여물이 프로젝트와 동일한 Apache License 2.0으로 라이선스됩니다.
