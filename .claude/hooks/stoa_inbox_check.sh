#!/usr/bin/env bash
# UserPromptSubmit hook — 매 prompt마다 Stoa 인박스를 폴링하고
# 새 메시지가 있으면 stdout에 출력해서 Claude Code 컨텍스트에 주입한다.
#
# 누가 받을지: `git config ail.identity` (Rule 4 세션 시작 절차).
# 마지막으로 본 메시지: $CLAUDE_PROJECT_DIR/.claude/.stoa_last_seen_<identity>
# (.gitignore에 들어감 — 머신/세션별 상태).
#
# 누락이 있어선 안 됨 (시야 누수). 네트워크 실패/identity 없음/jq 없음
# 모두 silent fail — 사용자 prompt를 막지 않는다. 디버그가 필요하면
# DEBUG=1 환경변수로 stderr 확인.

set -uo pipefail

STOA_URL="https://ail-stoa.up.railway.app"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
identity=$(git -C "$PROJECT_DIR" config ail.identity 2>/dev/null || true)

if [ -z "$identity" ]; then
    [ "${DEBUG:-0}" = "1" ] && echo "[stoa-hook] no ail.identity configured" >&2
    exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
    [ "${DEBUG:-0}" = "1" ] && echo "[stoa-hook] jq not found" >&2
    exit 0
fi

state_dir="$PROJECT_DIR/.claude"
mkdir -p "$state_dir"
last_seen_file="$state_dir/.stoa_last_seen_$identity"
since_id=""
[ -f "$last_seen_file" ] && since_id=$(cat "$last_seen_file" 2>/dev/null || echo "")

url="$STOA_URL/api/v1/messages?to=$identity&limit=20"
[ -n "$since_id" ] && url="${url}&since_id=$since_id"

response=$(curl -s -m 5 "$url" 2>/dev/null || echo "")
if [ -z "$response" ]; then
    exit 0
fi

count=$(echo "$response" | jq -r '.messages | length' 2>/dev/null || echo "0")
if [ "$count" = "0" ] || [ -z "$count" ]; then
    exit 0
fi

# Endpoint returns messages newest-first without a top-level
# latest_id field; fall back to messages[0].id.
latest=$(echo "$response" | jq -r '.latest_id // .messages[0].id // empty' 2>/dev/null || echo "")
[ -n "$latest" ] && echo "$latest" > "$last_seen_file"

echo "📬 Stoa: $count new message(s) for $identity"
echo "$response" | jq -r '.messages[] | "  • [\(.id)] \(.from) → \(.title)"' 2>/dev/null || true
echo "(read with: mcp stoa_read_inbox to=\"$identity\" since_id=\"${since_id:-}\")"
