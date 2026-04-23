# ail-herald

AIL과 HEAAL을 자기 자신으로 홍보하는 에이전트. **AIL로 작성된 agent가 AIL을 홍보합니다.**

이 프로젝트는 세 개의 primitive만 조합합니다:
- `intent` — 게시글 본문 작성 (언어 모델 위임, v1.10.0 harness가 타입 검증)
- `perform env.read` — Discord webhook URL을 환경변수에서 안전하게 읽기 (하드코딩 금지)
- `perform http.post` — 승인 후 실제 게시

사람의 승인이 **보안 경계**이고, 승인 이후의 실행은 전부 자율입니다.

## Behavior
- POST body="draft" → 새 초안을 `intent`로 생성, state에 저장, 초안 텍스트 반환
- POST body="publish" → 저장된 초안을 환경변수 `AIL_HERALD_DISCORD_WEBHOOK`의 Discord 채널에 게시, 결과 반환
- POST body="" (또는 그 외) → 현재 저장된 초안 조회

## Setup
Discord 서버의 채널 설정 → Integrations → Webhooks → New Webhook → URL 복사. 그리고:

```bash
export AIL_HERALD_DISCORD_WEBHOOK=https://discord.com/api/webhooks/.../...
ail up reference-impl/examples/agentic/ail-herald
```

## Tests
- 없음 (실제 Discord webhook이 필요한 end-to-end 에이전트)

## Deployment
- 포트 8080
