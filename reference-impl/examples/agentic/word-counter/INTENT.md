# word-counter

A small HTTP service that counts words in incoming text. Returns the
number on its own line. Empty input is an error, not a zero.

## Behavior
- Trim whitespace before counting
- Empty input or whitespace-only input → error
- Inputs longer than 10000 characters → error (too long)

## Tests
- "hello world" → succeed
- "the quick brown fox" → succeed
- "   " → 에러
- "" → 에러

## Deployment
- 포트 8080
