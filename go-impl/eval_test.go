package main

import (
	"strings"
	"testing"
)

// runSrc compiles and runs an AIL source string with the given input,
// returning the entry result's value (stringified) or failing the test.
// No adapter is configured, so programs containing intents will fail —
// these tests cover only the pure-fn path.
func runSrc(t *testing.T, src, input string) string {
	t.Helper()
	toks, err := NewLexer(src).Tokenize()
	if err != nil {
		t.Fatalf("lex: %v", err)
	}
	prog, err := NewParser(toks).ParseProgram()
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	val, err := NewEvaluator(prog, nil).Run(input)
	if err != nil {
		t.Fatalf("run: %v", err)
	}
	return toText(val.V)
}

func TestFactorial(t *testing.T) {
	got := runSrc(t, `
        fn factorial(n: Number) -> Number {
            if n <= 1 { return 1 }
            return n * factorial(n - 1)
        }
        entry main(x: Text) { return factorial(6) }
    `, "")
	if got != "720" {
		t.Fatalf("factorial: want 720, got %q", got)
	}
}

func TestFibonacci(t *testing.T) {
	got := runSrc(t, `
        fn fib(n: Number) -> Number {
            if n <= 1 { return n }
            return fib(n - 1) + fib(n - 2)
        }
        entry main(x: Text) { return fib(10) }
    `, "")
	if got != "55" {
		t.Fatalf("fib(10): want 55, got %q", got)
	}
}

func TestFizzBuzzMatchesPython(t *testing.T) {
	// Exact string match with what the Python reference produces.
	// See reference-impl/examples/fizzbuzz.ail — the spec is the
	// source of truth, both runtimes conform to it.
	src := `
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
            n = to_number(limit)
            if n == false { n = 15 }
            return fizzbuzz_range(n)
        }
    `
	want := "1, 2, Fizz, 4, Buzz, Fizz, 7, 8, Fizz, Buzz, 11, Fizz, 13, 14, FizzBuzz"
	got := runSrc(t, src, "15")
	if got != want {
		t.Fatalf("fizzbuzz: mismatch\n want %q\n  got %q", want, got)
	}
}

func TestStringOps(t *testing.T) {
	got := runSrc(t, `
        entry main(x: Text) {
            parts = split("a,b,c,d", ",")
            return join(parts, "-")
        }
    `, "")
	if got != "a-b-c-d" {
		t.Fatalf("got %q", got)
	}
}

func TestListMembership(t *testing.T) {
	got := runSrc(t, `
        entry main(x: Text) {
            xs = [1, 2, 3]
            return 2 in xs
        }
    `, "")
	if got != "true" {
		t.Fatalf("got %q", got)
	}
}

func TestHeterogeneousEqualityIsFalseNotError(t *testing.T) {
	// Matches Python semantics: comparing a number to a bool yields false
	// rather than raising. Programs written against the reference
	// runtime rely on this (e.g. `if n == false { ... }` as a cheap
	// "did to_number fail?" probe).
	got := runSrc(t, `
        entry main(x: Text) {
            n = 5
            if n == false {
                return "bug"
            }
            return "ok"
        }
    `, "")
	if got != "ok" {
		t.Fatalf("got %q", got)
	}
}

func TestParseErrorReportsLocation(t *testing.T) {
	_, err := NewParser(mustTokenize(t, "fn oops( { }")).ParseProgram()
	if err == nil {
		t.Fatal("expected parse error")
	}
	if !strings.Contains(err.Error(), "parse error") {
		t.Fatalf("unexpected error shape: %v", err)
	}
}

func mustTokenize(t *testing.T, src string) []Token {
	t.Helper()
	toks, err := NewLexer(src).Tokenize()
	if err != nil {
		t.Fatalf("lex: %v", err)
	}
	return toks
}

func TestJSONParsingTolerance(t *testing.T) {
	// Matches the tolerance matrix of the Python shared parser.
	cases := []struct {
		in    string
		wantV interface{}
		wantC float64
	}{
		{`{"value": "hi", "confidence": 0.9}`, "hi", 0.9},
		{"```json\n{\"value\": \"hi\", \"confidence\": 0.8}\n```", "hi", 0.8},
		{"Here: {\"value\": \"Seoul\", \"confidence\": 0.95} hope it helps.", "Seoul", 0.95},
		{`{"value": "x", "confidence": 1.5}`, "x", 1.0},
		{`{"value": "x", "confidence": -0.2}`, "x", 0.0},
	}
	for _, c := range cases {
		v, conf := parseValueConfidence(c.in)
		if v != c.wantV || conf != c.wantC {
			t.Errorf("input %q -> (%v, %v); want (%v, %v)", c.in, v, conf, c.wantV, c.wantC)
		}
	}
}
