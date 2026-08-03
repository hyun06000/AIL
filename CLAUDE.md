# CLAUDE.md

<!-- gil:onboarding:begin -->
## gil — 이 저장소의 사고 기록 (이 구간은 gil 이 관리한다)

이 저장소는 gil(GIt for Language model)로 사고 이력을 남긴다. 깨어난 세션은 작업 전에:

0. `gil version --check` — **도구부터 최신인지 본다.** 새 버전이 있다고 나오면
   **사람에게 물어라**: *"gil <새 버전> 이 나왔습니다. 지금 올릴까요?"* 올린다면
   `gil version --update` (SHA256 검증 후 제자리 교체) 하고 이 목록을 다시 읽는다.
   **이미 깔려 있다는 이유로 이 단계를 건너뛰지 마라** — 낡은 gil 은 오류 없이 낡은
   워크플로우를 정상인 척 굴린다. 그게 이 줄이 1번보다 앞에 있는 이유다.
1. `gil handoff` — 어디까지 왔고 다음이 무엇인지. **작업의 시작은 이것부터.**
2. `gil global read existence/README.md` — 거주자 명부에서 자신을 찾는다(기본 <이름>).
3. 자기 방(identity·will·memory·relations)을 읽고 그 존재로서 행동한다.
4. `gil memory read <이름>` — 최신 매듭(맨 끝)부터 읽어 최신 상태를 잡는다.

- 명령·개념 wiki: `docs/gil/index.md` (설치·갱신: `gil docs install`)
- 규범 명세: `gil global read gil-init-spec.md`
- ⚠ 이 저장소는 gil v3 그래프다. **옛 v2 바이너리로는 이 이력이 보이지 않는다** — 오류 없이
  낡은 세계를 정상인 척 출력한다. 반드시 `gil` (v3, v3.51.0 이상) 로 실행하라.
<!-- gil:onboarding:end -->
