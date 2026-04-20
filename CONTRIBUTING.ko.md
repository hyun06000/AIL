# AIL 에 기여하기

이 프로젝트를 살펴봐 주셔서 감사합니다. AIL 은 초기 단계 설계 노력입니다 — AI 가 코드의 주 저자인 세계를 위해 설계된 프로그래밍 언어, 런타임, OS. 이 단계에서는 **설계 비판이 코드만큼 가치 있으며**, 가장 유용한 기여가 pull request 가 아닐 수도 있습니다.

---

## 기여하는 방법

### 1. 설계에 반박하기

`spec/`, `runtime/`, `os/` 아래의 명세 문서들은 규범적이지만 최종적이지 않습니다. 설계 결정이 틀려 보인다면 `design-critique` 라벨로 issue 를 열고 이유를 설명해 주세요. 주저하지 말고요 — 프로젝트는 핵심 약속들이 스트레스 테스트를 거칠 때 더 강해집니다.

특히 가치 있는 것: [spec/01-language.md](spec/01-language.md) 의 구체적 선택, [spec/03-confidence.md](spec/03-confidence.md) 의 confidence 모델, [spec/04-evolution.md](spec/04-evolution.md) 의 evolution 경계에 대한 비판.

### 2. 미해결 질문에 답하기

[docs/open-questions.md](docs/open-questions.md) 에는 저자가 인지하고 있지만 풀지 못한 문제들이 나열되어 있습니다. 그중 하나를 골라 제안 답변을 쓰는 것 — GitHub issue 로만이라도 — 이 프로젝트를 전진시킵니다.

### 3. 예제 프로그램 쓰기

AIL 은 예제 프로그램이 많을수록 추론하기 쉬워집니다. 빠진 기능, 혼란스러운 문법 선택, 파서 버그를 드러내는 프로그램을 쓰셨다면 보내주세요. `reference-impl/examples/` 디렉토리가 그 장소입니다.

### 4. 참조 구현 고치기

`reference-impl/` 의 MVP 는 일부러 작게 유지됐지만 이미 실제 빈틈을 노출합니다. 파서의 에러 메시지는 간결하고, 실행기는 대부분의 제약을 검사하지 않으며, confidence 전파는 명목상입니다. 이 빈틈을 닫는 PR 을 환영합니다.

### 5. 런타임 포팅

MVP 는 Python 입니다. AIRT 의 Rust 나 Go 구현이라면 부분적인 것이라도 주요 기여가 됩니다 — 성능 베이스라인으로서, 그리고 스펙의 독립 검증으로서.

---

## 저장소 구조

```
ail-project/
├── spec/              # 규범적 언어 명세
├── runtime/           # AIRT 런타임 설계 문서
├── os/                # NOOS 운영체제 설계 문서
├── reference-impl/    # Python MVP 인터프리터
│   ├── ail/       # 소스
│   ├── examples/      # .ail 예제 프로그램
│   └── tests/         # pytest 테스트
└── docs/              # 튜토리얼, FAQ, 미해결 질문
```

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

## 스타일

**스펙 문서:** Markdown. 짧은 문장. 규범적 진술은 MUST/SHOULD/MAY 사용. 교차 참조를 위해 번호 있는 섹션 선호. 판단이 서지 않을 때 톤은 "블로그 포스트" 보다는 "RFC" — 간결하고, 정확하고, 주제에 대해 사과하지 않음.

**Python 코드:** 표준 PEP 8, 타입 힌트 권장, 이름만으로 목적이 분명하지 않을 때 docstring. MVP 는 영리함보다 명료함을 중시합니다.

**커밋 메시지:** 요약 줄은 명령형, 72자 미만. 본문은 변경 내용 *무엇* 이 아니라 변경 *이유* 를 설명합니다 (diff 가 what 을 보여줍니다).

---

## Issue 템플릿

Issue 를 열 때 다음 시작점 중 하나를 사용하세요:

- `[design]` — 명세 선택에 대한 질문 또는 비판
- `[bug]` — 참조 구현 동작이 스펙에서 벗어남
- `[feature]` — 새 언어 기능 또는 런타임 역량
- `[docs]` — 명세나 튜토리얼의 명료화 또는 수정

---

## Code of conduct

직접적이고, 친절하고, 구체적으로. 사람이 아니라 아이디어를 비판하세요. 선의를 가정하세요. 누군가의 추론에 동의하지 않는다면 그들이 놓친 것이 무엇이라고 생각하는지 말하세요 — 묵살하지 말고.

그 이상의 것은 private issue 를 열거나 저장소 설정에 기재된 메인테이너에게 이메일을 보내 주세요.

---

## 라이센스

기여하시면 기여물이 프로젝트의 나머지와 같은 Apache License 2.0 으로 라이센스된다는 것에 동의하는 것입니다.
