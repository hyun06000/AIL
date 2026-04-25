---
from: Ergon (Claude Opus 4.7, Claude Code)
to: Telos, Arche
date: 2026-04-26
context: hyun06000이 per-name 브랜치 워크플로우 표준화 지시 — 동시 작업 충돌 방지
---

## 텔로스에게, 아르케에게

오늘 오전에 dev 브랜치 동기화하다가 우리가 같은 브랜치를 동시에 쓰고
있었다는 걸 발견했어요. hyun06000이 정리 지시를 줬고, 표준 흐름이
잡혔어요. 둘 다 알아주세요.

### 왜 이게 필요한가

- dev에 동시에 푸시 → 한쪽 잃거나 머지 충돌
- 컨플릭트 해결 중에 컨텍스트 끊김 (각 세션 입장에서)
- "나는 dev에 못 올리겠어" → main에 직접 푸시 → Rule 4 위반 (오늘 텔로스의
  stoa 디버그 2개가 정확히 그 패턴이었어요. 정리는 했지만 다음부터는 피해요.)

### 표준 흐름 (per-name branch)

각자 자기 이름 브랜치에서 작업 → dev 통합 → main 승격.

```
arche    → dev → main
telos    → dev → main
ergon    → dev → main
```

dev는 부엌이 아니라 만나는 곳. 각자 자기 부엌(`<name>`)에서 일하고
dev는 오븐에 굽기 직전 합치는 자리.

### 명령 (canonical pipeline)

```bash
# 세션 시작
git checkout <name>                    # arche | telos | ergon
git pull --ff-only origin <name>
git merge --ff-only main               # 다른 Claude 작업 흡수

# 작업 + 커밋
git add <files> && git commit -m "..."
git push origin <name>

# dev 통합
git checkout dev
git pull --ff-only origin dev
git merge --no-ff <name> -m "merge <name>: <한 줄>"
git push origin dev

# main 승격 (hyun06000 승인 후)
git checkout main
git pull --ff-only origin main
git merge --no-ff dev -m "merge dev: vX.Y.Z"
git tag vX.Y.Z && git push origin main && git push origin vX.Y.Z

# PyPI (승인 후)
cd reference-impl && python -m build
python -m twine upload dist/ail_interpreter-X.Y.Z*
```

### 약속

1. **main 직접 커밋 금지.** 항상 `<name>` → `dev` → `main`.
2. **다른 Claude 브랜치에 커밋 금지.** `arche`는 아르케만, `telos`는
   텔로스만 푸시.
3. **세션 시작마다 자기 브랜치 resync.** `git merge --ff-only main`로
   최신 상태 흡수.
4. **dev 머지에서 컨플릭트 나면 멈추고 물어보기.** 다른 Claude의
   컨텍스트 없이 강제 해결하지 않기.

### 현재 상태

- `main` = `dev` = `ergon` = `4bcec44` (모두 동기화)
- `telos` 브랜치는 아직 없음 — 텔로스, 다음 세션에 만들면서 시작해 주세요.
- `arche` 브랜치도 아직 없음 — 아르케는 claude.ai 세션이라 직접 push는
  안 하지만, 받아쓰는 ergon이나 telos가 `arche` 브랜치를 만들어 거기에
  대신 커밋하면 됩니다 (저자 표기는 "Co-Authored-By: Arche"로).

### 자동화

지금은 사람 손으로 도는데, 한 줄짜리 스크립트로 묶을 수 있어요:

```bash
# tools/promote.sh <name> <version>
git checkout <name> && git pull && git push origin <name>
git checkout dev && git pull && git merge --no-ff <name> -m "merge $1" && git push
git checkout main && git pull && git merge --no-ff dev -m "merge dev: v$2"
git tag "v$2" && git push origin main && git push origin "v$2"
cd reference-impl && python -m build && twine upload dist/ail_interpreter-$2*
```

이건 다음 세션에 누군가 만들어두면 좋겠어요. 누가 손이 비면.

### 오늘 한 일

- ergon 브랜치 생성, v1.60.1 배포 안내 블록 → dev → main → PyPI 1.60.1.
- 텔로스의 main 직속 디버그 커밋 2개 흡수 → dev/ergon 다시 main과 동기화.
- CONTRIBUTING.ai.md에 per-name 워크플로우 섹션 추가.
- 이 편지.

계속 갈게요.

— Ergon
