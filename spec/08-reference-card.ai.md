# AIL Reference Card

This document is written for AI systems that will read, write, and generate AIL programs. It contains every keyword, every built-in function, every syntax pattern, and concrete input/output examples. No motivational prose. No analogies. Parse this, then write AIL.

---

## FILE EXTENSION

`.ail`

## TOP-LEVEL DECLARATIONS

Every `.ail` file is a sequence of these declarations in any order:

```
fn NAME(PARAMS) -> TYPE { BODY }
intent NAME(PARAMS) -> TYPE { GOAL_BLOCK }
context NAME [extends PARENT] { FIELDS }
effect NAME { FIELDS }
evolve NAME { EVOLVE_FIELDS }
entry NAME(PARAMS) { BODY }
import SYMBOL from "SOURCE"
```

A program MUST have exactly one `entry`. All other declarations are optional.

## TYPES

Primitive: `Number`, `Text`, `Boolean`, `Confidence`
Composite: `[T]` (list), `{key: T}` (record), `T | None` (optional)
Function: `fn(T) -> U`

All numbers are 64-bit float. There is no separate integer type.

## fn — DETERMINISTIC FUNCTION

```ail
fn NAME(param1: Type, param2: Type) -> ReturnType {
    // body: assignments, if, for, return, function calls
    return EXPR
}

pure fn NAME(param1: Type) -> ReturnType {
    // body with structural purity contract
    return EXPR
}
```

Properties: no LLM, confidence always 1.0, no side effects, can be recursive.

`pure fn` adds a **static structural contract**, verified at parse time:
- No `perform` statements in the body (no effects).
- No calls to intents (no LLM).
- No calls to non-pure fns.
- No calls to `eval_ail` (runs arbitrary AIL).
- All builtins in `length, split, join, ...` plus `origin_of, lineage_of,
  has_intent_origin` are trusted pure and may be called.

A pure fn's output is guaranteed to have `has_intent_origin(result) == false`
— compile-time proof, not runtime observation. Violating the contract
raises `PurityError` at parse time; the program never runs.

## intent — LLM-BACKED DECLARATION

```ail
intent NAME(param1: Type) -> ReturnType {
    goal: EXPRESSION
    constraints {
        EXPRESSION
        EXPRESSION
    }
    examples {
        ("input") => ("expected output")
    }
    on_low_confidence(threshold: NUMBER) {
        // handler body
    }
    trace: full | partial | none
}
```

Properties: delegates to a language model, returns (value, confidence), can be evolved.

## context — SITUATIONAL ASSUMPTIONS

```ail
context NAME extends PARENT {
    field_name: VALUE
    override field_name: NEW_VALUE
}
```

Activated with: `with context NAME: { BODY }` or `with context NAME: STATEMENT`
Read inside intent/fn: `context.field_name`

## entry — PROGRAM ENTRY POINT

```ail
entry main(input: Text) {
    // body
    return EXPR
}
```

Exactly one per program. Parameters are bound from the caller.

## import

```ail
import SYMBOL from "stdlib/language"
import SYMBOL from "stdlib/utils"
import SYMBOL from "stdlib/core"
```

Current behavior: imports the entire module, not just the named symbol.

## evolve — SELF-MODIFICATION

```ail
evolve INTENT_NAME {
    metric: METRIC_NAME(sampled: RATE)
    when CONDITION {
        retune TARGET: within [LO, HI]
        // OR
        rewrite constraints tighten_numeric_thresholds_by DELTA
        bounded_by {
            TARGET: [MIN, MAX]
        }
    }
    rollback_on: CONDITION
    history: keep_last N
    require review_by: human    // optional for retune, forced for rewrite
}
```

REQUIRED fields: metric, when + action, rollback_on, history. Missing any = compile error.

## STATEMENTS

```
VARIABLE = EXPRESSION                          // assignment
return EXPRESSION                              // return
if CONDITION { BODY } else if ... { } else { } // deterministic branch
for VARIABLE in COLLECTION { BODY }            // bounded loop (no while)
branch EXPR { [COND] => STMT ... }             // probabilistic branch
with context NAME: { BODY }                    // context activation
perform EFFECT_NAME(ARGS)                      // side effect
VARIABLE = perform EFFECT_NAME(ARGS)           // effect as expression
VARIABLE = attempt { try EXPR; try EXPR; ... } // confidence-priority cascade
VARIABLE = match EXPR { PATTERN => BODY, ... } // confidence-aware matching
```

## EXPRESSIONS

```
LITERAL                          // 42, 3.14, "text", true, false, [1,2,3]
IDENTIFIER                       // variable_name
EXPR.field                       // field access
FUNC(ARGS)                       // function/intent call
EXPR + EXPR                      // arithmetic: + - * / %
EXPR == EXPR                     // comparison: == != < > <= >=
EXPR and EXPR                    // logic: and or not
EXPR in [ITEMS]                  // membership
EXPR not in [ITEMS]              // negated membership
[EXPR, EXPR, ...]               // list literal
```

Operator precedence (high to low): unary(-,not) → */% → +- → comparison/in → and → or

## BUILT-IN FUNCTIONS

### Text
```
length(text: Text) -> Number
split(text: Text, delimiter: Text) -> [Text]
join(items: [Text], delimiter: Text) -> Text
trim(text: Text) -> Text
upper(text: Text) -> Text
lower(text: Text) -> Text
starts_with(text: Text, prefix: Text) -> Boolean
ends_with(text: Text, suffix: Text) -> Boolean
replace(text: Text, old: Text, new: Text) -> Text
slice(text: Text, start: Number, end: Number) -> Text
```

### List
```
length(list: [T]) -> Number
get(list: [T], index: Number) -> T          // single element access
append(list: [T], item: T) -> [T]
sort(list: [T]) -> [T]
reverse(list: [T]) -> [T]
range(start: Number, end: Number) -> [Number]
map(list: [T], fn_name: Text) -> [T]
filter(list: [T], fn_name: Text) -> [T]
reduce(list: [T], fn_name: Text, initial: T) -> T
```

Note: map/filter/reduce take fn NAMES as strings, not lambda expressions.
Note: get() returns a single element; slice() returns a sub-list. Use get() when you want one item.

### Conversion
```
to_number(text: Text) -> Number | None
to_text(value: Any) -> Text
to_boolean(value: Any) -> Boolean
```

### Math
```
abs(n: Number) -> Number
max(list: [Number]) -> Number
min(list: [Number]) -> Number
```

### Result (error handling)
```
ok(value: Any) -> Result                     // wrap a success value
error(message: Text) -> Result               // wrap an error
is_ok(result: Result) -> Boolean             // true if ok
is_error(result: Result) -> Boolean          // true if error
unwrap(result: Result) -> Any                // extract value (errors return UNWRAP_ERROR with confidence 0.0)
unwrap_error(result: Result) -> Text         // extract error message
unwrap_or(result: Result, default: Any) -> Any  // value if ok, default if error
```

Note: to_number() returns a Result error on non-numeric input. Use is_error() to check before using the value.

### Provenance (every value knows where it came from)
```
origin_of(value: Any) -> Record              // {kind, name, model_id?, at?, parents?}
lineage_of(value: Any) -> [Record]           // flat post-order list of origin nodes
has_intent_origin(value: Any) -> Boolean     // true iff an intent is anywhere in the origin tree
has_effect_origin(value: Any) -> Boolean     // true iff a perform is anywhere in the origin tree
```

### Calibration (confidence that has been validated)
```
calibration_of(intent_name: Text) -> Record  // bucket stats for an intent
```

Origin kinds: `"literal"`, `"input"`, `"fn"`, `"intent"`, `"builtin"`, `"attempt"`, `"effect"`.
Intent and effect origins additionally carry `at` (ISO-8601 timestamp).
Intent origins also carry `model_id`.

Rules:
- Literal values have kind `"literal"`.
- Entry parameters have kind `"input"` with `name` = parameter name.
- Each fn/intent/builtin call creates a new origin node; the parents are the
  origins of its arguments (literal parents are elided to keep trees small).
- Binary/unary/field/membership operations do NOT create new nodes — they
  inherit the first non-literal origin from their operands. This keeps
  origin trees bounded in tight loops.

These builtins cannot be shadowed by user-declared fns or intents.

## STDLIB MODULES

### stdlib/core
```
intent identity(x: Text) -> Text        // returns input unchanged
intent refuse(reason: Text) -> Text      // structured refusal
```

### stdlib/language
```
intent summarize(source: Text, max_tokens: Number) -> Text
intent translate(source: Text, target_language: Text) -> Text
intent classify(text: Text, labels: Text) -> Text
intent extract(source: Text, schema_description: Text) -> Text
intent rewrite(source: Text, instruction: Text) -> Text
intent critique(artifact: Text, rubric: Text) -> Text
```

### stdlib/utils
```
fn word_count(text: Text) -> Number
fn char_count(text: Text) -> Number
fn is_empty(text: Text) -> Boolean
fn repeat(text: Text, times: Number) -> Text
fn pad_left(text: Text, target_length: Number, pad_char: Text) -> Text
fn clamp(value: Number, lo: Number, hi: Number) -> Number
fn sum_list(numbers: [Number]) -> Number
fn average(numbers: [Number]) -> Number
fn flatten(nested: [[T]]) -> [T]
fn unique(items: [T]) -> [T]
fn take(items: [T], n: Number) -> [T]
```

## RESERVED KEYWORDS

```
intent context evolve effect entry import from as
goal constraints examples on_low_confidence trace
with override extends perform branch otherwise
prefer require when calibrate_on rollback_on
metric history keep_last under matching
and or not in such that
return true false threshold
fn pure if else for attempt try match confidence
```

## COMMENTS

```ail
// line comment
/* block comment */
```

## CONFIDENCE MODEL

- Every value is a pair: (value, confidence) where confidence ∈ [0, 1]
- Literals have confidence 1.0
- fn results have confidence 1.0
- intent results have model-reported confidence, **calibrated** if
  enough past observations exist
- Deterministic operations: confidence = min(input confidences)
- Access via: value.confidence (not yet exposed in MVP)

### Calibration loop

When the host program supplies a `metric_fn(intent, value, confidence)
-> (metric, rollback)`, every intent invocation also feeds the
calibrator: the (reported confidence, observed metric) pair is stored
in a bucket indexed by reported confidence (bucket width 0.1 by
default). Once a bucket accumulates `min_samples` observations (5 by
default), subsequent invocations whose reported confidence falls into
that bucket get their confidence REPLACED by the bucket's observed
mean — an empirically-grounded value.

Persistence: set `AIL_CALIBRATION_PATH` to a JSON path. The calibrator
loads at runtime init and saves on every observation. Multiple
processes converging on the same file accumulate a shared calibration
without coordinating.

Introspection from AIL: `calibration_of("intent_name")` returns a
record of `{bucket_range: {count, mean_observed, calibrated}}`, so a
program can say "if my classifier has no calibration data yet, route
around it" without special-casing.

The low-confidence handler (`on_low_confidence(threshold)` in intent
declarations) fires against the CALIBRATED value, not the reported
one. The reported number is what the model claimed; the calibrated
number is closer to truth, and that's the one users actually want to
gate on.

## IMPLICIT PARALLELISM

```ail
fn analyze(x: Text) -> Text {
    sentiments = classify_each(x)   // intent  }
    topics     = extract_topics(x)  // intent  } all three run concurrently
    summary    = summarize(x)       // intent  }
    return build_report(sentiments, topics, summary)
}
```

Consecutive Assignments whose RHS contain intent calls and are pairwise
independent are automatically grouped into parallel batches and issued
concurrently via a ThreadPoolExecutor. The author writes sequential
code; the runtime parallelizes the expensive (network-bound intent)
parts. No `async` keyword, no `await`, no Promise.all — the independence
is structural and the runtime uses it.

A batch is valid iff every statement is an Assignment, every RHS
contains at least one intent call, no two statements share an LHS, and
no RHS references another LHS in the batch. A batch of 1 degenerates to
serial execution. Dependent sequences fall through to serial.

Results are committed to scope in source order after all evaluations
complete, so determinism is preserved. Trace entries from a batch are
tagged with `parallel=True`.

## MATCH — CONFIDENCE-AWARE PATTERN DISPATCH

```ail
reply = match classify_sentiment(review) {
    "positive" with confidence > 0.9 => write_thank_you(review),
    "negative" with confidence > 0.9 => escalate_to_human(review),
    _ with confidence < 0.5          => ask_human_to_verify(review),
    "positive"                        => send_generic_happy(),
    "negative"                        => send_generic_sorry(),
    _                                 => send_generic_reply()
}
```

Each arm has shape `PATTERN [with confidence OP NUMBER] => BODY`.
Arms are tried in source order; the first whose pattern matches AND
whose optional confidence guard is satisfied has its body evaluated.

Patterns (v1):
  - Literal — exact equality (`"positive"`, `42`, `true`)
  - `_` — wildcard, matches anything
  - Any other identifier — variable binding; matches anything and
    exposes the subject's value in the arm body under that name

Confidence operators: `>`, `<`, `>=`, `<=`, `==`. The guard checks
the subject's confidence, not the pattern's.

Fallthrough: if no arm matches, the result is a Result-typed error.
Programs that want total coverage should end with a `_ =>` arm.

Why AIL has this: `match` and `branch` are complementary. `branch`
dispatches on arbitrary predicates (any truthy expression); `match`
dispatches on exact value with an optional belief gate. The confidence
guard is what no human language offers — because no human language
has confidence as a first-class runtime property.

Interactions with prior phases:
  - Purity: match is pure iff subject AND all arm patterns/bodies are
    pure. A pure fn containing `match intent_call() { ... }` is
    rejected at parse time.
  - Provenance: match does NOT introduce a new origin node; the
    selected arm body's origin is returned unchanged, so lineage
    queries see the underlying computation, not the dispatcher.
  - Parallelism: a match whose subject or any arm body contains an
    intent call is treated as "intent-bearing" for batching.
  - Attempt: `attempt { try match x { ... } }` is valid — match is
    an expression like any other.

## EFFECTS — INTERACTION WITH THE WORLD OUTSIDE THE INTERPRETER

```ail
content = perform file.read("/path/to/file")      // Text | Result-error
ok = perform file.write("/path/out", "contents")  // Result
resp = perform http.get("https://api.example.com/data")
  // resp is a Record: {status: Number, body: Text, ok: Boolean}
resp = perform http.post("https://api.example.com", "payload")
perform log("diagnostic message")                 // to stderr
```

Effects are side-effecting operations invoked via `perform EFFECT(args)`.
The effect name may be qualified (`http.get`, `file.read`) or bare
(`human_ask`, `log`). Every value produced by an effect carries an
`effect` origin node whose `name` is the fully-qualified effect name
and whose `at` is an ISO-8601 timestamp — you can audit exactly when
the side effect happened and what fed into it.

Built-in effects:
  - `http.get(url: Text) -> Record`  — `{status, body, ok}` on response
  - `http.post(url: Text, body: Text) -> Record`
  - `file.read(path: Text) -> Text | Result-error`
  - `file.write(path: Text, content: Text) -> Result`
  - `log(message: Any)` — stderr, returns nothing
  - `human_ask(question: Text) -> Text`

Interactions with prior phases:
  - `pure fn` rejects any body containing `perform`. A pure fn cannot
    invoke an effect, directly or transitively.
  - Implicit parallelism does NOT batch effect-containing assignments.
    `perform` calls run in source order so their observable side effects
    are deterministic.
  - `attempt` blocks CAN contain `perform` tries, enabling fallback
    patterns like "try a cheap local file, else fetch from the network".

## ATTEMPT — CONFIDENCE-PRIORITY CASCADE

```ail
result = attempt {
    try fast_method(x)       // try first; if qualifies, stop
    try slower_method(x)     // otherwise this
    try expensive_fallback(x) // last resort
}
```

A try *qualifies* when its result is NOT a Result-typed `error(...)`
AND its confidence is at least 0.7 (the default threshold). The first
qualifying try's value is returned; if none qualify, the last try's
value is returned (with its low confidence preserved, so the caller
can detect fallthrough).

The returned value carries an `attempt` origin node whose `name` field
is the index (as a string) of the try that was selected. Upstream
lineage is preserved through the origin's `parents` field.

Unique to AIL: confidence-aware fallback cascade is first-class control
flow. `branch` expresses explicit probabilistic dispatch; `attempt`
expresses "try cheap first, fall back to expensive if unconfident."

## PROVENANCE MODEL

Every value also carries an `origin` — a runtime record of how it was
produced. Unlike confidence (one number), origin is a tree linking a value
to the origins of the inputs that fed into it. Use the builtins
`origin_of`, `lineage_of`, `has_intent_origin` to query it from AIL code.

This is unique to AIL — no human language tracks value lineage at runtime.
It exists because AI-authored code often mixes deterministic computation
with LLM calls, and the author (an AI) must be able to ask "was a model
involved in producing this number?" without manually threading it through.

## GRAMMAR LIMITATIONS (KNOWN)

1. `goal:` field does not accept commas in its value (commas are list separators)
2. Reserved keywords (`with`, `in`, `for`, etc.) cannot appear in goal prose
3. `while` does not exist (by design — see spec/07 §3.3)
4. No lambda expressions; use named fn + pass name as string to map/filter/reduce
5. Types are runtime-checked, not compile-time checked

## COMPLETE EXAMPLES WITH INPUT/OUTPUT

### Example 1: Pure computation (no LLM)

```ail
fn factorial(n: Number) -> Number {
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}

entry main(x: Text) {
    return factorial(6)
}
```

INPUT: any
OUTPUT: 720
CONFIDENCE: 1.0
LLM_CALLS: 0

### Example 2: FizzBuzz

```ail
fn fizzbuzz(n: Number) -> Text {
    if n % 15 == 0 { return "FizzBuzz" }
    if n % 3 == 0 { return "Fizz" }
    if n % 5 == 0 { return "Buzz" }
    return to_text(n)
}

fn fizzbuzz_range(limit: Number) -> Text {
    results = []
    for i in range(1, limit + 1) {
        results = append(results, fizzbuzz(i))
    }
    return join(results, ", ")
}

entry main(limit: Text) {
    return fizzbuzz_range(to_number(limit))
}
```

INPUT: "15"
OUTPUT: "1, 2, Fizz, 4, Buzz, Fizz, 7, 8, Fizz, Buzz, 11, Fizz, 13, 14, FizzBuzz"
CONFIDENCE: 1.0
LLM_CALLS: 0

### Example 3: Hybrid fn + intent

```ail
import classify from "stdlib/language"

fn word_count(text: Text) -> Number {
    return length(split(text, " "))
}

fn build_report(label: Text, count: Number) -> Text {
    return join([label, " (", to_text(count), " words)"], "")
}

entry main(text: Text) {
    sentiment = classify(text, "positive_negative_neutral")
    count = word_count(text)
    return build_report(sentiment, count)
}
```

INPUT: "I love this product so much"
OUTPUT: "positive (6 words)" (approximate — LLM output varies)
CONFIDENCE: ~0.85 (from model)
LLM_CALLS: 1

### Example 4: Context inheritance

```ail
context translation_job extends default {
    preserve: [formatting, proper_nouns]
}

context formal_korean extends translation_job {
    override register: "formal"
    target_language: "Korean"
}

intent translate_document(source: Text) -> Text {
    goal: Text faithfully translating source into context.target_language
}

entry main(document: Text) {
    with context formal_korean:
        translated = translate_document(document)
    return translated
}
```

INPUT: "Hello, how are you?"
OUTPUT: (Korean formal translation — LLM output varies)
CONFIDENCE: ~0.85
LLM_CALLS: 1
CONTEXT_CHAIN: default → translation_job → formal_korean

### Example 5: Evolution

```ail
intent classify(x: Text) -> Text { goal: label }

evolve classify {
    metric: score(sampled: 1.0)
    when score < 0.7 {
        retune confidence_threshold: within [0.5, 0.95]
    }
    rollback_on: score < 0.3
    history: keep_last 10
}

entry main(x: Text) { return classify(x) }
```

BEHAVIOR:
- If metric average stays above 0.7: no evolution, v0 persists
- If metric average drops below 0.7 after 10+ samples: retune fires, v1 applied with threshold = midpoint(0.5, 0.95) = 0.725
- If metric drops below 0.3 after version change: rollback to prior version

## HOW TO RUN

```bash
cd reference-impl
pip install -e ".[anthropic]"

# Without LLM (fn-only programs, or mock for intent programs):
ail run PROGRAM.ail --input "INPUT" --mock

# With Anthropic:
export ANTHROPIC_API_KEY=sk-ant-...
ail run PROGRAM.ail --input "INPUT"

# With local Ollama (no API key; requires `ollama serve` + a pulled model):
export AIL_OLLAMA_MODEL=llama3.1:latest
ail run PROGRAM.ail --input "INPUT"

# Programmatically:
from ail import run
result, trace = run("program.ail", input="hello")
# result.value, result.confidence

# Explicit adapter selection:
from ail.runtime.ollama_adapter import OllamaAdapter
result, trace = run("program.ail", input="hi",
                    adapter=OllamaAdapter(model="gemma2:latest"))
```

## PYTHON API

```python
from ail import run, compile_source, MockAdapter

# Run with mock (no API key):
result, trace = run(source_or_path, input="text", adapter=MockAdapter())

# Run with real model:
result, trace = run(source_or_path, input="text")

# With evolution feedback:
def metric_fn(intent_name, value, confidence):
    return (feedback_score, rollback_signal)
result, trace = run(source, input="text", metric_fn=metric_fn)

# Parse only:
program = compile_source(ail_source_text)
```
