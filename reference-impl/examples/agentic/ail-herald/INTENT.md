# ail-herald

AIL과 HEAAL을 자기 자신으로 홍보하는 **대화형 에이전트**. AIL로 작성된 agent가 AIL을 홍보합니다.

**중요**: 사용자가 프로그래밍을 모르고, 웹훅이 뭔지도 모른다고 가정합니다. 필요한 게 있으면 에이전트가 먼저 묻고, 한 단계씩 안내합니다. 초기 설정 없이 바로 실행하세요.

## Flow

1. `ail up reference-impl/examples/agentic/ail-herald` 실행
2. 브라우저에서 `http://127.0.0.1:8080/` 열기
3. 에이전트가 인사하고 두 갈래를 제시:
   - **글만 받기** — 아무 설정 없이 바로 초안만 받아서 복붙
   - **Discord에 올리기** — 웹훅 없으면 "웹훅이 뭐냐면..." 부터 단계별 안내 → URL 붙여넣기 → 저장 → 게시
4. 각 단계마다 버튼으로 다음 진행 또는 뒤로가기

## Principles

- **Negotiate, don't presume** — 채널/자격증명을 코드에 하드코딩하지 않음. 사용자가 제공할 때까지 진행 안 함.
- **Plain-language onboarding** — "웹훅"같은 용어는 즉석에서 설명.
- **Human approval is the trust boundary** — 실제 게시는 "이대로 올리기" 클릭 시에만.
- **Reversible** — 언제든 "← 처음으로" 버튼으로 리셋.
- **Audit trail** — 모든 단계가 `.ail/ledger.jsonl`에 타임스탬프와 함께 기록.

## Architecture

- `app.ail` — state.read/write로 현재 step 추적하는 상태 머신. `entry main`이 list-of-pairs (`[["message", ...], ["action", ...], ...]`) 반환.
- `view.html` — 응답 JSON을 파싱해서 메시지 / 드래프트 / 버튼 / 입력필드로 렌더.
- `intent write_promo_post` — 실제 글쓰기 (v1.10.0 harness가 Text 강제).
- `perform env.read / state.read` — 웹훅 URL은 state(UI 붙여넣기) 또는 env var(CI)에서 읽음. 소스엔 절대 없음.
- `perform http.post` with `Content-Type: application/json` — 실제 게시.

## Tests
- (대화형 UI라 단위 테스트 대신 시나리오 스모크 테스트 권장)

## Deployment
- 포트 8080
