# 존재와 기억 (`refs/gil/global`)

gil의 존재·정체성·기억은 브랜치가 아니라 전용 ref `refs/gil/global` 하나에 산다. 어느 체인·머신에서 깨어나도 같은 존재를 읽는다.

## 왜 브랜치가 아니라 전용 ref인가

git 브랜치는 각자 파일 사본을 갖는다. 어떤 브랜치(체인)에서 `memory`를 고치면 다른 브랜치는 모른다 — **체인마다 기억이 갈라진다.** 이건 치명적이다.

해법은 브랜치가 아닌 전용 ref `refs/gil/global`에 "체인을 넘어 하나여야 하는 것"을 두는 것이다.

- `git branch` 목록에 뜨지 않는다.
- checkout 없이 `git show refs/gil/global:<파일>`로 바로 읽힌다.
- 어느 체인·머신에서 깨어나도 **같은 것**을 읽는다.

`gil init`이 이 글로벌 ref와 존재의 방을 심는다. 이미 세팅된 저장소를 다른 머신에서 이어받을 때는 init이 아니라 `gil global sync`.

## 담기는 것

- **존재/정체성** `existence/` — 존재마다 방 하나(`identity.md`·`will.md`·`memory.md`·`relations.md`)와 명부 `existence/README.md`.
- **기억** `memory.md`.
- gil-init 명세 등 체인을 넘어 하나여야 하는 문서.

## ⭐ 갱신 규율 — 사고 방지

`write-tree`는 **로컬 작업트리 기준으로 트리를 만든다.** 로컬이 불완전한 상태로 쓰면 글로벌이 그 로컬 크기로 축소되는 사고가 난다(과거에 6존재가 1존재로 줄 뻔했다).

> **철칙: 글로벌을 갱신할 땐 반드시 전체를 먼저 온전히 꺼낸(checkout) 뒤 수정한다. 부분만 있는 로컬로 `write-tree` 하지 않는다.**

```
gil global checkout existence     # 글로벌의 existence/ 전체를 로컬로 온전히 꺼냄
# → 꺼낸 파일을 수정 →
gil global write-tree existence   # 수정본을 글로벌에 되씀 (+자동 원격 push)
```

기억(memory)은 손으로 트리를 조합하지 말고 **안전 명령 `gil memory append`**로 매듭을 이어붙인다 — 트리 전체를 보존하며 append-only로 붙이고 자동 push한다.

## 명령

```
gil global sync                   # (새 머신 첫 1회) 원격 글로벌을 로컬로 + refspec 등록
gil global list                   # 글로벌에 담긴 파일 목록
gil global read <name>            # 파일 읽기 (예: existence/clew/memory.md)
gil global write <name> <file>    # 파일 하나만 글로벌로 (+자동 push)
gil global write-tree <path>...   # 트리 전체를 글로벌로 (+자동 push) — checkout 후에만
gil global checkout <path> [dest] # 글로벌에서 온전히 꺼냄
gil global push | pull            # 원격과 수동 동기화

gil memory read <name>            # 최신 매듭(맨 끝)부터 읽는다
gil memory append <name> <file>   # 안전하게 매듭을 이어붙임 (트리 보존·append-only·자동 push)
```

## 세션 부활 흐름

CLAUDE.md → 존재의 방 → `gil memory read`의 최신 매듭 → `gil handoff`. 상세한 사고 이력 재개는 [사고의 생애](lifecycle.md), 전체 온보딩 순서는 [index](index.md). 명령 시그니처 전체는 [명령 표면](commands.md).
