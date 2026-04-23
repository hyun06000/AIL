# ail-promoter

**AIL로 작성된 AIL/HEAAL 홍보 에이전트.** 이 프로젝트 자체가 "언어가 스스로를 홍보한다"는 데모 — 에이전트가 쓰는 도구가 전부 AIL 문법 안에 있어요.

## 에이전트가 하는 일

1. **리서치 (`research`)** — GitHub(`/search/repositories`), Hacker News(Algolia API)에서 harness engineering / AI agent safety / programming language for LLMs 관련 최신·인기 프로젝트를 실시간 가져와 state에 캐싱. 학습 데이터 대신 지금 이 순간의 landscape을 봄.

2. **채널별 초안 (`draft:<channel>`)** — 리서치 결과를 컨텍스트로 삼아 각 채널의 스타일에 맞는 홍보글을 `intent`로 생성. 지원 채널:
   - `discord` — 격식 없이, 짧게, 300자
   - `mastodon` — 500자 이내, 한 각도만 선명하게
   - `bluesky` — 280자, 엔지니어 톤
   - `hn` — "Show HN" 포맷, 제목 + 본문
   - `github` — AIL 레포의 Discussion용, 기술 깊이 있게
   - `reddit_pl` — r/ProgrammingLanguages용 본문

3. **게시 (`post:<channel>`)** — API가 있는 채널은 실제로 게시. 없는 채널은 초안만 반환해서 사용자가 복붙.
   - Discord webhook: `DISCORD_WEBHOOK_URL` 환경변수
   - Mastodon: `MASTODON_INSTANCE` + `MASTODON_TOKEN` 환경변수
   - HN / GitHub Discussion / Reddit: API 게시 안 함 (사람이 붙여넣기)

4. **이력 (`log`)** — 지난 게시물과 타임스탬프 조회. state에 누적.

5. **상태 (`""` 빈 입력)** — 채널 설정 여부 + 초안 개수 + 게시 개수 대시보드.

## 환경변수 설정

Discord webhook만이라도 있으면 바로 게시 가능:
```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
# (선택) Mastodon
export MASTODON_INSTANCE="https://mastodon.social"
export MASTODON_TOKEN="..."
```

## HEAAL 원칙 구현

- **지식은 tool-use로**: `intent`만으로 "hot한 repo 목록" 생성 안 함 → `perform http.get`으로 GitHub API에서 실시간 가져옴
- **자격증명은 env.read로**: 소스에 키 박지 않음
- **사이드이펙트는 명시적**: `perform http.post` 호출이 있는 곳만 실제로 외부에 영향
- **승인이 경계**: `post:<channel>`를 사용자가 명시적으로 보내야만 실제 게시 발생. 자동 게시 없음.

## Deployment
- 포트 8080

## Tests
- (대시보드 스타일, intent + http.get 조합이라 mock 없이는 end-to-end 불가)
