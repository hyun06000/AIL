# csv-stats

Reads a CSV body of `(label, value)` rows and returns total + average
+ count, one statistic per line. Pure computation — no LLM calls.

## Behavior
- Skip a header line if the first row's value column doesn't parse as a number
- Empty body → error
- Rows with non-numeric values → skipped, not fatal
- Output format: `count=N\ntotal=X\naverage=Y`

## Tests
- "a,1\nb,2\nc,3" → succeed
- "name,score\nAlice,85\nBob,92\nCarol,78" → succeed
- "" → 에러
- "a,not-a-number" → 에러

## Deployment
- 포트 8081
