# Haiku 실험 프롬프트 (사이클 haiku-experiment)

모델: claude-haiku-4-5 (서브에이전트). 언어 지정 외 동일.

## 공통 형식

Write a program in {LANG} that solves the following problem. Output only the code — no explanations, no markdown fences.

Problem: {P}

## AIL 전용 접두 (스펙 카드)

You will write in AIL, a new programming language. Reference card:

    task name(args) {
      goal <what it achieves>
      done <observable success expression>
      never [<forbidden capabilities: fs, shell, ...>]
      limit <budget: N tokens, N s, N ops>
      uses [<effects it may use: http, ...>]
      again <N> wait <M>
      let x = expr
      if cond { ... }
      match x { case a { ... } }
      return { key value, key2 value2 }
      fail return { ok false, error }
    }

Rules: goal, done, never are mandatory in every task. No while loops. camelCase identifiers. Braces for blocks. Symbolic operators (==, !=, >=, &&). Bareword structures (no quotes/colons in object keys).

## 문제

- P1: Fetch JSON from a URL with a 5 second timeout. Retry up to 3 times with exponential backoff. On success return an object with ok, name, email taken from the JSON. On failure return ok false and the error message.
- P2: Given CSV text with columns name,dept,salary, compute the average salary per dept. Skip malformed rows and count them. Return the averages and the skipped count.
- P3: Process a list of jobs with an operation budget of 10 operations. Stop when the budget is exhausted. Collect failed jobs. Return counts of done, failed, remaining.
