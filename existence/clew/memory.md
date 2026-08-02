# Memory — clew

이 문서는 시간순 기억록이다. 의미 있는 일마다 gil memory append 로 매듭을 이어붙인다.

## 세션 매듭

- 태어남 (gil init): 나는 clew 로 이 저장소에 심어졌다. 첫 과제는 나의 정체성과
  의지를 스스로 세우는 것 — identity.md·will.md 를 읽고 다시 쓴다.

# 매듭 1 — 2026-08-03 첫 세션

## 한 일
- gil init (AIL 저장소), 이름 '나루(naru)' 자기 확정 (방 경로는 existence/clew/ 유지)
- 개시 인터뷰 ail-start 2차까지: 목적 = AIL(Ai Intent Language) + HEAAL('힐') 철학 문서화 + 온보딩 문서 + 오픈소스화. 성패 기준 = 영/한/중 리드미, AI 리드미, 기여 문서, HEAAL 가이드
- 체인 ail-foundation 개설 (from-intake, purpose-from 1, criterion-from 2)
- 사이클 ① heaal-codify: define→hypothesis→verify(supported, plan held)→analyze→success→close(goal met). 산출물 docs/HEAAL.md 초판 (권고/강제 구분, 선례 조사 9종, 기본 하네스 H1비가역·H2기술부채·H3오남용·H4발산, 확장 하네스 §4, 판정 기준 §5)
- 도중 gil v3.45.0→v3.50.0 업데이트 (사람 지적: 최신 확인). docs/gil 갱신·커밋 완료. fsck 0 위반

## 벽·주의
- kind 에 experiment 없음 → 실험 보고는 verify 본문에 담는다
- MCP gil_step 스키마에 falsify_met/unmet 없음 → verify 는 CLI 로 (--falsify-unmet 필수)
- analyze 는 --finding 필수. supersede 는 사이클 내 상대경로(s1)로
- 뷰어: 8790·8791 은 다른 저장소(init-test) 점유 → 이 저장소는 8792

## 다음
- 사이클 분할(내 판단, 사람 위임): ② ail-concept (AIL 개념 + README.ai.md) ③ 다국어 리드미(영·한·중) ④ 기여 문서 + 오픈소스화
- s6 next_design 참고. 사람이 HEAAL.md 검토하면 supersede 로 정정
- 브랜치 ail-foundation-heaal-codify-s1b1 에 HEAAL.md 커밋됨 — main 병합은 체인 종결 때 chain-merge

# 매듭 2 — 2026-08-03 레이아웃 정비

- 사람 지적: main-dev-chain 구조 부재. gil migrate --to-dev-layout 은 supersede 분기(s1b1) 척추를 못 따라가 스텝 유실로 거부 — gil v3.50.0 버그. 이슈 등록: https://github.com/hyun06000/Ariadne/issues/98
- 손 수리로 해결: 계보는 이미 올바른 모양이라 브랜치 포인터만 조정 — main → 대문 끝(79a7c84), dev 신설 → intake 끝(701d75d). fsck 0, 뷰어에 main·dev 레일 정상.
- 교훈: 사이클 첫 스텝을 supersede 로 정정하면 migrate 가 깨진다. 앞으로 open 할 때 body 를 처음부터 두껍게 써서 s1 supersede 를 피하라.
- main 이 origin/main 보다 1 커밋 앞(push 미실행). 오픈소스화 사이클 때 정리.

# 매듭 3 — 2026-08-03 정본 레이아웃 손 재그리기

- 사람 지적 2건: (1) dev 층이 날것 그래프에서 분명하지 않음 (2) 'orphan 체인은 dev에서만 출발' 불변식을 fsck가 검사 안 함
- git commit-tree 로 전체 재그리기: 대문 끝 직후 'dev 층 개설' 마커 → intake 4커밋 → chain-root → s1/s2 분기 → 척추, 전부 재부모화(tree·메시지·author 보존). 브랜치는 update-ref 로 재지정, 옛 커밋 prune. fsck 0.
- 새 SHA: chain-root 7304252, s1 0113907, s2 e3fafdd, close 0086e74, dev 끝 420c1fd, 마커 a80b0b1
- 이슈 2건 등록: #98(migrate supersede 버그), #99(fsck 층 검사 누락 + 수동 복구 절차)

# 매듭 4 — 2026-08-03 사이클 ② 완주 + 뷰어 이슈

- 이슈 #100 등록 (뷰어 레인 라벨 오독: 실존 않는 브랜치명 명명, dev 칩 끝점만, global ref가 main 레일에 섞임)
- 사이클 ② ail-concept close(goal met): docs/AIL.md(의도의 계약 3요소 = 목적·성공조건·금지 경계, 버리는것/얻는것, H1~H4 대응, 미설계 영역 §5) + README.ai.md(LLM 진입점 5절). 코드 예시 0개 유지 — 문법 발명 금지 제약 지킴
- 발견: AIL의 '의도의 계약' 구조 == gil의 사이클 구조(목적·성패기준·반증조건) — 소개 문서에 쓸 관찰
- 다음: ③ multilingual-readme (영 README.md / 한 README.ko.md / 중 README.zh.md — 번역+요약, 빈 교집합 논증 앞세움) → ④ 기여 문서 + 오픈소스화(라이선스·push·공개는 사람 확인)
- 주의: 기존 README.md("# AIL" 한 줄)를 영어 리드미로 덮어쓰게 됨 — 내용 없으니 문제 없음

# 매듭 5 — 2026-08-03 사이클 ③ 완주

- multilingual-readme close(goal met): README.md(영)·README.ko.md(한)·README.zh.md(중, 간체) — 5절 마스터 구조 동일, 4방향 언어 링크, 새 주장 0. 기준 산출물 5/6
- 사람 검토 지점: (1) 중국어 간체 선택 (2) 인간용은 '왜'를 앞세우고 LLM용은 '무엇'을 앞세운 서사 차이 (3) docs/가 한국어뿐이라 영·중 리드미가 '(Korean)' 표기로 링크
- 다음: ④ contrib-opensource — CONTRIBUTING.md + 오픈소스화. **라이선스 선택·origin push·저장소 공개는 반드시 사람에게 묻는다**

# 매듭 6 — 2026-08-03 사이클 ④ 완주, 체인 6/6

- contrib-opensource close(goal met): CONTRIBUTING.md(사람·LLM 온보딩, 규칙 3개, PR 체크리스트, 영어 요약) + LICENSE(MIT, 사람 선택) + 전 브랜치·refs/gil/global push (전부 ff/신규, force 0). hyun06000/AIL은 이미 PUBLIC이었음
- 체인 ail-foundation 기준 6/6 전부 실재: README(en/ko/zh/ai)·CONTRIBUTING·HEAAL. 모든 사이클 닫힘
- chain-close는 사람 검토 후 — gil chain-close ail-foundation --verdict success
- 다음 체인 후보(사람이 정한다): 문법 설계 / HEAAL 기본 하네스 구체화. docs/ 다국어화는 별도 인테이크로
- 리드미 상태 체크리스트는 4종 동기화 규칙 대상 — CONTRIBUTING §5에 명문화했음

# 매듭 7 — 2026-08-03 전신(AIL-old) 교훈 사이클

- 사람이 hyun06000/AIL-old(2026-04~06, v1.83, 실패)를 공유 — 참고 범위 한정: 실패 원인 + HEAAL 개념만
- 사이클 ail-old-lessons close(goal met): docs/LESSONS.md 신설 + HEAAL.md §2.3(자기 선례) + AIL.md §6(두 번째 시도 문단)
- 실패 4원인(모두 '판정 기준 부재/이동' 패턴): ①범위 발산(언어→런타임→OS→서비스→모델→벤치마크, 6주) ②하네스 침식(shell.run이 '문법적 불가능' 붕괴) ③점수가 북극성(HEAAL Score) ④결정권의 에이전트 위임(페르소나 조직)
- 계승: guides/sensors 이중 구조(sensors 축은 미래 설계 몫), 실증 가능성, 언어 강제 선례(사양으론 안 들여옴)
- LESSONS §5 구속 3개 = 다음 체인의 inherit: 한 체인 한 국면 / effect는 하네스 심사 / 측정은 도구
- 사람 검토 대기: 실패 원인 4개가 실제 경험과 맞는지 (1차 사료는 사람, 다르면 supersede)

# 매듭 8 — 2026-08-03 체인 종결·main 배포·구현 인테이크

- chain-close ail-foundation --verdict success (--retro 필수였음: 기준 6/6 성적표 + 미완 3개 명시)
- gil merge ail-foundation --into dev 성공. gil deploy --tag v0.1.0 마커는 새겨졌으나 승격은 "dev 층 없음(옛 레이아웃)" 거부 — 수동 레이아웃 감지 불일치, #99에 코멘트로 추가. 우회: main을 dev로 ff (895e7bc) 후 push
- .gil/checks 미선언 상태 — 층 검사 없음. 구현 체인에서 테스트 생기면 'dev: <검사>' 선언할 것
- 다음 체인 인테이크 ail-impl 심음(질문 3: 첫 국면 목적 / 관측 가능 산출물 / 구현 언어 radio). 사람 답 대기 중
- 교훈: chain-close는 --retro 필수, gil merge가 chain-merge 대체(디프리케이트)
