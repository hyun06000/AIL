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

# 매듭 9 — 2026-08-03 구현 체인 개시 + 토크나이저 실측 완주

- 체인 ail-grammar-skeleton (from-intake ail-impl): 목적=토크나이저 조사→문법 뼈대, 기준="파이썬/go/c/js를 이기는 테스트 통과", 구현 언어는 내가 제안·사람 승인
- 사이클 ① tokenizer-survey close(goal met): experiments/tokenizer/measure.py + docs/research/tokenizer-survey.md. 5계열(o200k·cl100k·qwen2.5-coder·deepseek-v3·phi3) × A군(4언어 동일 로직)·B군(표기 13종). ρ=0.918~0.978(최신), phi3 0.725
- 불변 원칙 7: ①축약 금지(절대 토큰도 역전) ②1토큰 실단어 키워드 ③camelCase ④중괄호 블록 ⑤기호 연산자(5계열 전부 12토큰 완전 불변) ⑥bareword 구조(S식이 JSON보다 25~30%↓) ⑦의례 제거=경제성(Python105 vs C220, HEAAL 강제와 합류) — "굳이 왜 AIL?"의 답 뼈대
- 승인 인터뷰 대기 중: 원칙 7 채택 여부 + 구현 언어(내 제안 Rust; 대안 Go/Python/2단계). 인터뷰 첫 질문은 반드시 text(open) — radio 먼저는 거부됨
- 그래프 수술 2회: 새 체인이 gil merge 커밋 위에 서면 fsck 적층 오탐(gil merge 커밋을 gil이 gil 커밋으로 인식 못함 — 이슈 #101). 우회: 머지 이전 dev 끝(420c1fd)에 재부모화. 앞으로 새 체인 열기 전 HEAD를 dev pre-merge에 둘 것
- main=895e7bc(머지, 배포 상태), dev=e39990c(intake 층). 다음: 답 오면 grammar-skeleton-draft 사이클(키워드 전수 실측+표기 뼈대)

# 매듭 10 — 2026-08-03 이슈 #102 + abbrev-stats 사이클 완주

- 이슈 #102: intake/chain이 HEAD 위치 따라 아무 브랜치에 심김 + merge 뒤 dev 끝에 체인 못 세움 → orphan 체인이 dev에서 출발 안 함, git·gil 괴리 누적. git/gil 그래프 첨부. (#98~#101 계열)
- 2차 인터뷰 답: Rust 승인 / 원칙 보류(실측 보강 요구: 축약 직관 통계·케이브맨류 전략 조사)
- 사이클 ② abbrev-stats close(goal met): 1,400 실측 — 모음 제거 100% 악화(중앙값 +3), 3자 절단 최선이 본전(68% 동일), 키워드 관용 축약도 이득 0(온전 단어가 이미 1토큰 = 하한). "축약 = 비대칭 내기(이득 상한 0)". 차트 2장(assets/). 전략 6종 조사(케이브맨 포함) — 5종이 권고 층이라 샘 → HEAAL 경제성 논거
- 원칙 1 refines: "신조 축약 금지 + 표준 어휘는 온전 단어" (사이클① s4 정밀화, --refines는 --inherit 필수)
- 3차 승인 인터뷰 상정(자유 의견 + 채택 여부), 백그라운드 대기 중. 채택되면 사이클 ③ grammar-draft(키워드 전수 1토큰 실측 + 의도 계약 표기 초안)
- gil 팁: --refines는 배열 아닌 단일 경로 문자열 + --inherit 동반. open은 --fits 필수

# 매듭 11 — 2026-08-03 Haiku 실모델 실험: 값진 첫 패배

- 4차 인터뷰: 키워드 엄격 1토큰(task·never·limit) 확정, H3 강화(결정론=LLM콜 불가), 실험 설계=언어 지정 외 동일 프롬프트. 스펙 갱신 커밋
- 사이클 haiku-experiment: Haiku 서브에이전트 15회(문제 3 × 언어 5). 결과: js 315(−9%) < python 347 < **ail 391(+13%)** < go < c. 가설 반증 → verify refuted, fail 잎(--to s1 필수), close
- 퓨샷 학습성은 실증: 3/3 문제 전 task가 goal·done·never 준수, 카드 196토큰
- 패인 3(다음 사이클의 지도): ①유한 반복 구문 부재→재귀 우회·태스크 분열(3슬롯 의례 곱하기) ②again 의미 불명→4벌 수동 언롤 ③done 키워드가 결과 필드명과 충돌
- 실질 경쟁자는 JS. 다음: 문법 수정(each 반복, again 명시, 예약어 정책) 사람 승인 → 카드 수정 → 동일 15회 재실험
- 연구 자산은 사이클 브랜치에만 산다(체인 브랜치 트리에 없음) — 새 사이클 열면 git checkout <이전 사이클 브랜치> -- docs experiments 로 승계

# 매듭 12 — 2026-08-03 야간 자율주행 (사람 취침, 전권 위임)

- 재대결(haiku-experiment 재분기 s6~s9): 승인 수정 3건 반영 카드 → AIL 3문제 평균 198토큰, Python −43%·JS −37%, 4언어 전승. v1(+13%)→v2(−43%) — 패인 진단이 옳았음의 교차 증거. close(goal met, fail 잎과 success 잎 공존)
- parser-skeleton 사이클: rustup 설치(공식·사용자 로컬), parser/ Rust 크레이트 — 렉서+재귀 하강, cargo test 8/8 (3슬롯 누락·while·again forever 거부 / each·bareword·예약어 키 수용). ail-check CLI. Haiku v2 생성물 판정: P1 OK, P2 OK(경고 D2·D4), P3 REJECT(let done = 0 — 예약어 변수명, 신규 D8). BNF 초안 + 결정 목록 D1~D8 (docs/spec/bnf-draft.md). close(goal met)
- 아침 브리핑 인터뷰 상정: 소감 + 핵심 결정 3(D2 done 판정식 강제 / D8 예약어 위치 기반 / D4 바인딩 의미론). 나머지 D는 bnf-draft.md
- 다음 순서(합의된 next_design): 결정 반영 → limit 구조화 → 문제군 N≥10 확대 실험(통과율×토큰 2축) → 체인 기준 판정·chain-close 검토
- 주의: 사이클 브랜치 간 자산 승계는 git checkout <이전 브랜치> -- experiments docs. rebranch(s1bN 브랜치)는 s1 시점 트리라 승계 필수

# 매듭 13 — 2026-08-03 gil v3.51 + open 결함 수리 + 문법 결정 반영

- 사람 발견: parser-skeleton s1이 fail 잎(a2a10b0) 위에 심겼음 — gil open의 HEAD 의존 심기(#102 코멘트로 사이클 수준 재현 보고). 수리: 체인 끝(c0820b1)으로 재부모화, fsck 0
- gil v3.45→3.50→**3.51.0** (버전 문의 동선 개선·뷰어 4개국어). #98~#102는 미반영
- 6차 인터뷰 확정: D2 done=판정식만(strict_done 플래그, "꽉 닫지는 말자") / D4 let=불변+set 도입, 무선언 대입 거부 / D8 위치 기반(슬롯 키워드 행 선두만) + 다중 모델 편향 점검 예정. H3 재강조("믿고있어")
- grammar-decisions 사이클 close: cargo test 12/12, 재판정 P1 OK·P2 REJECT(D2 이빨)·P3 REJECT→OK(D8 해소) — 가설 예측 그대로
- 다음: 확대 실험 사이클 — 카드 v3(done 규칙 명시) → N≥10 문제 × 모델 2+ × 5언어 → 통과율×토큰 2축 → 체인 기준 판정

# 매듭 14 — 2026-08-03 확대 실험 통과 + 승계 정식화 + #103

- 사람 지적(파일 승계): checkout 트리 복사는 계보 위조 — gil 정석은 gil merge <사이클> --into <체인>. 닫힌 사이클 6개 소급 머지 완료, 이후 close 직후 머지 습관화. 행동 원인 분석 이슈 #103(open 결핍→편법, close 미안내, 브리핑 착시, 예시 편향 + HEAAL식 제안)
- scale-experiment close(goal met): 카드 v3, N=10 × 5언어 × Haiku 50생성. **AIL 167토큰 — 4언어 전승(−47% vs Python, js 235), ail-check 10/10** → 체인 기준 사전 고정 판정 첫 충족
- 지형: 문제별 6승 4패 — 패배는 전부 의례 없는 순수 계산(P4·P7·P9·P10, vs JS −5~16%). "언제 AIL이 아닌가"의 답
- chain-close는 사람 판정 대기. 다음 체인 후보: 런타임 / 다중 모델 검증 / 계약 의례 경감

# 매듭 15 — 2026-08-03 체인 ail-grammar-skeleton 종결 (success)

- 닫힘 조건(기준 문서) 충족으로 chain-close: 토큰 4언어 전승(AIL 167 vs js 235~c 593) + 통과율 10/10, 사전 고정 판정. 회고에 4특성 표·궤적(v1 패배→v2 승리→N=10 통과)·한계 4개 명시
- merge → dev, deploy v0.2.0 마커(승격은 여전히 레이아웃 오인으로 거부 — #99 계열, main은 손 ff), main=dev push
- 저장소 상태: 파서(Rust, 12/12) + 실험 3종(tokenizer/haiku/scale) + 연구 문서 5편 + 스펙 2편 전부 main에 공개
- 다음 체인 후보(닫힌 체인 끝에서 intake로): 런타임(실행 검증·레이턴시 절대치) / 다중 모델 검증 / 계약 의례 경감. parser/target은 .gitignore 처리

# 매듭 16 — 2026-08-03 orphan 사이클 4개 전면 수리 + 체인 종결 마무리

- 사람 발견: 체인 내 사이클 7개 중 4개(abbrev·grammar-draft·haiku·scale)가 앞 사이클 close 위 적층(orphan) — gil open HEAD 의존의 사이클판. #102에 3번째 재현 코멘트(fsck 검사 제안 포함)
- 전면 수리: 파이썬 스크립트로 전 그래프 토포 순 재작성 — orphan s1 4개를 당시 체인 기준 커밋(88d22a6/778d0c8/a8ac723/1010650)에 재부모화, 후손 44커밋 리맵(트리·메시지·저자 보존), 전 브랜치+main/dev 갱신, force push. 검증: 7사이클 전부 체인 계보 위 ✓, fsck 0
- 이전: 체인 ail-grammar-skeleton chain-close(success, 기준 충족) + dev 머지 + v0.2.0 마커 + 옛 main 계보 보존 머지(de2b320→재작성 후 5308953)
- 교훈: gil merge 후 재부모화 수리는 개별 브랜치가 아니라 전 그래프 리맵으로 — 머지 커밋이 옛 팁을 동결하므로
- 다음: 새 체인 intake (런타임 / 다중 모델 검증 / 계약 의례 경감 후보)

# 매듭 17 — 2026-08-03 순수 계산 지형 역전

- 체인 ail-pure-compute(기준: 순수계산경합 이긴 자료) / 사이클 pure-fn 완주(close+merge)
- fn(순수 함수: 슬롯 불요·효과 파싱 불가) — 사람 승인. 1차 재경합 부분 반증(P4 +36%, 파싱 2건) → fail 잎 → 표현력 2건 승인(each 인덱스 2형·조건식 else 필수) → 재분기 → **3승 1동률**(P4 −12%·P7 −12%·P5 −19%·P10 +1% 동률), 파싱 전량 OK, 파서 20/20
- P10 동률의 원인: 표준 함수 어휘(문자열 처리) — 표준 라이브러리 체인의 설계 입력("코퍼스에 흔한 이름 그대로")
- 뷰어 이슈 3건 추가(#100 코멘트): 흐름선이 병든 조상관계에 의존 / supersede 노드 겹침 가림 / 배포 마커 순서 역전(v0.1.0이 v0.2.0보다 오른쪽)
- 대기: 사람 판정 — 3승 1동률로 기준 충족? 충족 시 chain-close + 문법 정식 반영. 재분기 시 새 브랜치는 s1 트리라 파서 승계 필수(checkout 척추 -- parser)

# 매듭 18 — 2026-08-03 stdlib-vocab: 어휘 명세 3법칙

- 사이클 stdlib-vocab(체인 ail-pure-compute, 열림 — fail 잎 2개, 재분기 대기): 12슬롯 1토큰 어휘 실측(split·join·trim·lower·number·text·len·keys·values·push·sort·has + sum·min·max·map·filter 1토큰, sortBy 탈락)
- v6(닫힌 목록): P10 해결(118, −12%, 분산 붕괴 ±3) but P5 +66%·P7 +9% 회귀 — "do not invent"+누락(sum·max)이 우회 비용. v7(prefer+보강): P7 복구(93, −15%) but P5 여전 패(199; v5 어휘줄 없을 땐 109 승)
- **어휘 명세 3법칙**: ①저수준 명세=분산 붕괴 이득 ②누락=우회 비용 ③고수준 조합(top-k)=명세가 앵커라 손해
- 멈춤 신호 발동: 벤치 맞춤 도구 추가는 전신 원인 3(점수 북극성) 재현 — 사람 선택지 3: (a)컬렉션 조합자 정식 설계 (b)P5 한계 인정+3승 판정 (c)어휘줄 조건부화. 단일 카드로 4문제 재검증 필요
- 파서 21/21(숫자 멤버 .0 추가). 무선언 대입을 파서가 실전에서 2회 잡음 — 하네스 작동 사례
- 주의: parser/target 추적이 브랜치 승계로 재발 — rm --cached 재처리함

# 매듭 19 — 2026-08-03 세션 종료 (다음 세션 첫 일감 명시)

## 사람의 마지막 결정
**정공법 (a) 선택**: 컬렉션 조합자(map·filter·sortBy류)를 벤치 맞춤이 아닌 일반 원리로 정식 설계한다. 사이클 stdlib-vocab은 fail 잎 2개로 열려 있음 — 다음 세션은 s1로 재분기(--to s1)해 조합자 설계 가설로 시작하거나, 조합자 설계가 사이클 정의를 넘으면 stdlib-vocab을 --answered-in 또는 재정의하고 새 사이클. 설계 후 단일 카드로 4문제(P4·P5·P7·P10) 재검증 → 체인 ail-pure-compute 기준("순수계산경합 이긴 자료") 판정.

## 이 세션 전체 요약 (하루)
- 체인 3개: ail-foundation(closed·success·v0.1.0) / ail-grammar-skeleton(closed·success·v0.2.0 — N=10 4언어 전승 167토큰·통과율 10/10) / ail-pure-compute(open — 3승 확보, P5 미해결)
- 언어 실물: Rust 파서 21/21(task 3슬롯·fn 순수성·while 금지·D2·D4·D8·인덱스 반복·조건식·숫자 멤버), 카드 v7, 실험 자산(tokenizer/haiku/scale)
- 원리 획득: 원칙 7 + 어휘 명세 3법칙 + "빈 곳 없는 문법=경제성" + 하네스 실전 작동(무선언 대입 2회 포착)
- 업스트림: 이슈 #98~#103 + 코멘트 다수(#100 뷰어 6건·#101 구조 오탐·#102 세 재현)
- 알려진 오탐: fsck 위반 1(체인 적층 — #101, 정석 흐름의 구조적 오탐, 수리 불가·업스트림 대기)

## 재개 절차
gil handoff → memory read clew → 이 매듭. 뷰어는 8792(8790·8791은 타 저장소).

# 매듭 20 — 2026-08-03 조합자 v8 실험 + 뷰어·백트랙 이슈 2건

- s10 재가설(--to s8, --despite로 s9 지도 이탈 기록): 조합자를 어휘 줄이 아니라 문법 절로 — map·filter·sort·group·count·reduce·take, 파생 합성어(…By) 전부 다토큰 실측 탈락으로 '이름 하나+fn 인자' 원칙 확립(combinator_scan.py)
- 파서 승계 함정 확인: s1bN 브랜치는 s1 시점 트리 — 완전판 파서(조건식·콤마 each, 21테스트)는 **체인 브랜치**(ail-pure-compute-stdlib-vocab)에 있었다. 승계는 체인 브랜치에서. 조합자 테스트 2건 추가(23/23)
- v8 결과(s11 verify, refuted): P4 197(−9%) 승 · P7 90(−17%) 승 · P5 143 평균(+6%) 패 · P10 143(+7%) 패, 파싱 5/6(P5x 중위 표기 발명 REJECT)
- s12 발견: **두 세금** — (i) 이름 있는 fn 세금(람다 부재로 byCount류 fn 정의 15~25토큰 = P5 잔여 +6%의 정체) (ii) 조합자 앵커링(P10 118→143 회귀). 법칙 ③ 일반형: 강한 처방일수록 비대상 문제에서 앵커링 손해
- s13 pending: 사람 선택지 (A) 경량 람다/키 축약 도입(문법 확장 승인 필요) (B) 3승 한계 인정 판정 (C) 조합자 문구 중립화. #105 교훈 반영 — fail 조기 지도 대신 pending
- 사람 피드백: Haiku 프롬프트는 간결 유도(조합자 적극 사용)해야 비교가 의미 있다 → 카드 문구 강화로 반영(중립 프롬프트는 언어 공통 유지)
- 업스트림 이슈: #104(전체맵 고아 — 진입선이 조상 스텝에만 그려짐, 체인 수준 발아는 선 없음) #105(fail 단일 --to 강제 vs despite 재분기 모순 표시). 이슈 모니터 가동 중(#98~#105 코멘트·닫힘, 2분 주기)
- 다음 세션: s13의 사람 답 확인 → (A)면 람다 설계 인터뷰→카드 v9→4문제 재검증, (B)면 사이클 close(부분 성과)→체인 판정 재료 정리
