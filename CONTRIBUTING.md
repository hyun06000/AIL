# Contributing to AIL

이 문서는 사람과 LLM 에이전트 모두를 위한 기여 안내다. (English summary at the bottom.)

## 1. 이 저장소의 작동 방식

이 저장소는 [gil](https://github.com/hyun06000/Ariadne) (GIt for Language model)로 돈다.
모든 작업은 커밋 그래프에 **체인(목적) > 사이클(문제) > 스텝**으로 기록된다:

```
define(문제 정의) → hypothesis(가설 + 반증 조건) → verify(검증 + 판정)
→ analyze(해석 + finding) → success / fail (종결)
```

결론만 커밋되지 않는다. 가설이 왜 세워졌고, 무엇이 관측되면 틀리며, 실제로 무엇이
관측됐는지가 전부 남는다. 실패한 가지도 지워지지 않는다 — 벽의 지도는 다음 기여자의 자산이다.

레이아웃: `main`(대문·배포) → `dev`(모든 작업의 시작 층, 인테이크·인터뷰가 여기 쌓임) →
체인 브랜치(`<chain>`) → 사이클 브랜치(`<chain>-<cycle>`). 모든 체인은 dev에서 출발한다.

## 2. 사람 기여자 온보딩

1. [README.ko.md](README.ko.md)(또는 [README.md](README.md))와 [docs/HEAAL.md](docs/HEAAL.md), [docs/AIL.md](docs/AIL.md)를 읽는다 — 무엇을, 왜 만드는지.
2. [gil을 설치](https://github.com/hyun06000/Ariadne#readme)하고 저장소를 클론한다.
3. `gil handoff` — 열린 체인·사이클·다음 동작을 파악한다.
4. `gil viewer serve` — 브라우저에서 사고 그래프 전체를 본다.
5. 제안·질문은 GitHub 이슈로. 문서 오탈자 같은 작은 수정은 일반 PR로도 좋다.

## 3. LLM 에이전트 온보딩

[README.ai.md](README.ai.md) §4가 너의 진입점이다. 요체:

1. `cat CLAUDE.md` → `gil handoff` 로 위치를 복원한다
2. 새 작업은 `gil intake <슬러그> --ask ...` 로 **사람에게 물어** 시작한다 — 목적·성공 기준을
   받고 그 답을 **인용**해 체인을 연다. 목적을 창작하지 마라
3. 사이클을 완주한다: define부터 종결까지, 판정은 가설이 심은 반증 조건에 비추어
4. 끝나면 `gil memory append` 로 다음 세션에 매듭을 남긴다

## 4. 규칙 (전부 이 체인의 실천에서 온 것이다)

1. **사람의 답이 기준이다.** 체인의 목적·성패 기준은 인테이크/인터뷰의 답에서 인용된다.
   요약·정제도 창작이다 — 기준 문서(reference-*.md)를 다시 쓰지 마라.
2. **실패한 가지를 지우지 마라.** fail 잎과 backtrack은 기록이다. 히스토리 재작성(force push,
   rebase)은 금지다.
3. **데모 사이클을 만들지 마라.** 모든 사이클은 실제 문제로 연다.

## 5. PR 체크리스트

- [ ] `gil fsck` 위반 0 (그래프 무결성)
- [ ] 작업이 열린 체인의 기준 문서(레퍼런스 트루스)와 정합
- [ ] 리드미 내용을 바꿨다면 4종(en·ko·zh·ai) 동기화
- [ ] force push 없음
- [ ] 문서의 주장에 원천이 있음 (docs/ 또는 gil 그래프의 스텝)

---

## English summary

This repo runs on [gil](https://github.com/hyun06000/Ariadne): all work is recorded as
chain (purpose) > cycle (problem) > steps (define → hypothesis → verify → analyze → conclusion)
in the commit graph, failed branches included. **Humans**: read the readmes and docs, install gil,
run `gil handoff` and `gil viewer serve`, open issues for proposals. **LLM agents**: start at
[README.ai.md](README.ai.md). Rules: the human's answers are the reference truth (never rewrite
`reference-*.md`); never delete failed branches or rewrite history; no demo cycles. PR checklist:
`gil fsck` clean, consistent with the open chain's reference, readmes (en·ko·zh·ai) kept in sync,
no force push, every claim traceable to docs/ or a gil step.
