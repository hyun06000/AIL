# 사고의 생애: 스텝 흐름과 분기

한 사이클 안에서 스텝이 define→hypothesis→verify→analyze로 흐르고, 막혔을 때 어떻게 되돌아가 형제 가지를 뻗으며, 사이클을 어떻게 닫는지를 다룬다.

## 스텝 흐름

한 사이클은 스텝들이 이어지며 굴러간다. 스텝에는 **종류(kind)** 가 있고, 정해진 순서로 흐른다:

```
define ──▶ hypothesis ──▶ verify ──▶ analyze ──▶ success (산 잎)
(문제정의)   (가설)         (검증)      (분석)      └▶ fail   (죽은 잎)
                                                  └▶ pending(사람 대기)
```

- **define** (s1): 이 사이클이 풀 문제를 정의. `gil open`이 자동으로 만든다.
- **hypothesis**: 가설을 세운다. **가설 없는 공부는 스텝이 아니다** — 능동적으로 가설을 세워라.
- **verify**: 가설을 검증한다(실행·실험·테스트).
- **analyze**: 결과를 **분석**한다(순수 분석 — 판정은 다음 종결 스텝에서).
- **종결 스텝** — 분석 다음, 이 가지가 어떻게 끝나는지를 *별도 스텝*으로 커밋한다:
  - `--kind success` → **산 잎**(성공, 정답에 닿음). 본문에 문제정의부터 누적한 보고서를 담는다.
  - `--kind fail --to <조상 define>` → **죽은 잎**(실패·벽). 되돌아갈 곳을 `--to`로.
  - `--kind pending` → **사람 대기**. 이후 `gil approve`/`gil reject`만 허용된다. [사람과의 소통](human-in-the-loop.md) 참고.

(하위호환: 옛 `analyze --outcome success|backtrack|fail` 도 계속 인정된다.)

종결 스텝의 본문은 뷰어에서 마크다운으로 렌더되는 **보고서**다 — 짧게 쓰지 마라. [스텝 본문은 보고서다](reports.md)를 보라.

## 막혔을 때

예기치 못한 벽(성능·반증·결함)에 부딪히면 **접근을 조용히 갈아타지 않는다.** 방식을 슬그머니 바꾸는 것은 철칙 위반이다. 반드시:

1. **`analyze --outcome backtrack --to <조상 define>`** 으로 벽을 **죽은 잎**에 새긴다. 벽을 그래프에 데이터로 못박아야 재현되고, 다음에 같은 벽을 되풀이하지 않는다(= 벽의 지도).
2. 그 조상 **define으로 되돌아가** 문제를 재정의한다.
3. **`hypothesis --to <그 define>`** 으로 **새 형제 가지**를 뻗어 다른 길로 나아간다.

```
gil step demo/c001 --kind analyze --outcome backtrack --to s1 --title "벽: 62초 성능 한계"
gil step demo/c001 --kind hypothesis --to s1 --title "다른 접근: 일괄 파싱"   # s1의 새 형제
```

`hypothesis --to <define>`는 그 define 커밋에서 형제 가지 브랜치(`<chain>-<cycle>-<define>b<n>`)를 실제로 분기한다.

### 산 잎과 죽은 잎

- **산 잎**(analyze/success) = 성공한 가지. 나중에 머지·close의 대상이다.
- **죽은 잎**(backtrack/fail) = 실패한 가지. **지우지 않는다** — 벽의 지도로 영원히 남는다. 같은 벽을 두 번 물지 않기 위해서다.

### 가지 사이를 오가기

형제 가지는 진짜 git 브랜치라, 지금 어느 가지에 서 있느냐가 **무엇을 조상으로 볼 수 있느냐**를
정한다. 죽은 가지 끝에 서면 산 가지의 analyze 는 조상이 아니므로 `--to` 로 지목할 수 없다.
자리를 옮기는 것은 `gil goto` 다:

```
gil goto demo/c001            # 이 사이클의 산 잎으로 돌아간다
gil goto demo/c001/s5         # 그 스텝 자리로
```

그래프는 바뀌지 않는다(HEAD 만 움직인다). `gil handoff` 는 죽은 가지에 서 있으면 그 사실을
맨 위에서 먼저 알린다 — 갇혔다는 것을 다음 거부를 기다려서야 알지 않도록.

## 사이클 닫기

산 잎(analyze/success)이 하나라도 있으면 사이클을 닫을 수 있다:

```
gil close demo/c001 --verdict supported     # --verdict 기본값: supported
```

산 잎이 없으면 close가 거부된다 — 풀리지 않은 문제를 닫을 수 없다.

## 관련

- 세 위계와 순서 규칙: [체인·사이클·스텝](concepts.md)
- 종결 스텝 본문 작성: [스텝 본문은 보고서다](reports.md)
- pending으로 사람 대기·승인/기각: [사람과의 소통](human-in-the-loop.md)
- 명령 시그니처·플래그: [명령 표면](commands.md)
- 목차: [index](index.md)
