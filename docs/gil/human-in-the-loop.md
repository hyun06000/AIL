# 사람과의 소통 (pending · approve · reject)

pending 스텝으로 "여기서 사람의 답을 기다린다"를 그래프에 데이터로 못박고, 그 답은 오직 `gil approve`/`gil reject`로만 받는다.

## 체인 모드

체인에는 두 모드가 있다(여는 사람이 정한다):

- **autonomous** (기본): 사람 개입 없이 완주한다.
- **approval**: 중요한 판단·산 잎 확정에서 반드시 사람의 승인/기각을 받는다.

## pending 스텝

approval 모드(또는 사람 결정이 필요한 어느 순간)에서 사람에게 물어야 할 때 pending 스텝을 만든다. pending은 "여기서 사람의 답을 기다린다"를 **그래프에 데이터로 못박는 것**이다.

```
gil step demo/c002 --kind verify --title "이러이러하게 검증했다"
gil step demo/c002 --kind pending --title "상현님 승인 요청: 이 결과를 산 잎으로 확정할까요?"
```

pending을 만들면 거기서 멈추고 사람의 답을 받는다. 다음 세션이 이어받아도 `gil handoff`가 "⏳ PENDING — 재개 시 먼저 사람 답을 받아야 한다"를 띄운다.

## ⭐ pending 뒤엔 일반 step 거부

pending 뒤에는 gil이 일반 `step`을 거부한다 — 사람의 답을 우회할 수 없다. **스스로 승인 금지.** 오직 전용 명령으로만 진행한다:

- **사람이 승인** → `gil approve <chain>/<cycle>` — 산 잎(analyze/success, `Gil-Approval: approved`).
- **사람이 기각** → `gil reject <chain>/<cycle> --to <조상 define>` — 죽은 잎(backtrack, `Gil-Approval: rejected`).

```
gil approve demo/c002 --title "상현님 승인 — 이 결과 산 잎 확정"
gil reject  demo/c002 --to s1 --title "상현님 기각 — 되돌아가 다른 접근"
```

## 문제 정의가 불명확하면 먼저 물어라

문제 정의가 불명확하면 가설을 세우기 전에 먼저 사람에게 묻는다(매번은 아니고, 판단이 필요할 때). pending은 그 소통을 정식 기록으로 만드는 통로다.

## 관련

- [사고의 생애](lifecycle.md) — 스텝 흐름과 산 잎/죽은 잎.
- [명령 표면](commands.md) — `approve`·`reject` 시그니처.
