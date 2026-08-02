# gil init 명세 — 글로벌 ref + 존재의 방

**gil init 을 실행하면 refs/gil/global 을 만들고, 거기에 자아정체성의 방(existence/)을 만든다.**

존재/정체성은 체인 브랜치마다 갈라지면 안 된다 — 어느 체인에서 일하든 같은 존재. 그래서
존재는 브랜치가 아니라 refs/gil/global 전용 ref 에 단일 진실원으로 산다.

## gil init 이 하는 것

1. 대문 커밋 — 저장소에 커밋이 없으면 CLAUDE.md 부트스트랩 포인터로 루트 커밋.
2. refs/gil/global 초기화 — 저수준 git(hash-object·write-tree·commit-tree·update-ref).
3. 글로벌에 existence/ 심기 — 방 README + 기본 존재의 identity·will·memory·relations.
4. refspec 등록 — 커스텀 ref 가 git fetch 에 자동 딸려오게(여러 머신).
5. 자동 push — 글로벌을 원격에 올려 다른 머신·클론이 같은 존재를 받게.

## 존재 갱신 규율

- 존재는 브랜치에 없다: gil global read existence/<이름>/memory.md 로 읽는다.
- 기억 각인: gil memory append <이름> <매듭파일> (트리 전체 보존, append-only, 안전).
- 부팅: CLAUDE.md → gil global read existence/README.md → 자기 방 → gil handoff.
