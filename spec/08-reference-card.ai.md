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
```

Properties: no LLM, confidence always 1.0, no side effects, can be recursive.

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
append(list: [T], item: T) -> [T]
sort(list: [T]) -> [T]
reverse(list: [T]) -> [T]
range(start: Number, end: Number) -> [Number]
map(list: [T], fn_name: Text) -> [T]
filter(list: [T], fn_name: Text) -> [T]
reduce(list: [T], fn_name: Text, initial: T) -> T
```

Note: map/filter/reduce take fn NAMES as strings, not lambda expressions.

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
fn if else for
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
- intent results have model-reported confidence
- Deterministic operations: confidence = min(input confidences)
- Access via: value.confidence (not yet exposed in MVP)

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

# With LLM:
export ANTHROPIC_API_KEY=sk-ant-...
ail run PROGRAM.ail --input "INPUT"

# Programmatically:
from ail_mvp import run
result, trace = run("program.ail", input="hello")
# result.value, result.confidence
```

## PYTHON API

```python
from ail_mvp import run, compile_source, MockAdapter

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
