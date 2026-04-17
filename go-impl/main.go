// ail-go — a native AIL interpreter in Go.
//
// This is the second reference implementation of AIL, written independently
// of the Python interpreter. Both runtimes target the same language spec
// at spec/08-reference-card.ai.md. The Go build has zero external
// dependencies (stdlib only) and compiles to a single static binary —
// AIL programs can run without Python installed anywhere on the system.
//
// This runtime covers the Phase-0 subset of the spec: fn, entry, intent,
// primitive types, arithmetic, comparisons, if/else, for loops, lists,
// membership operators, and a core builtin set. Purity contracts,
// provenance, attempt, evolve, context, and implicit parallelism are
// owned by the Python implementation for now; bringing them over is the
// roadmap for the Go runtime.
//
// Usage:
//
//   ail-go run PROGRAM.ail [--input "INPUT"] [--model MODEL]
//
// The --model flag (or AIL_OLLAMA_MODEL env var) selects the ollama model
// used for intent dispatch. If neither is set and the program contains
// intents, the run will fail with a helpful error.
package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "run":
		runCmd(os.Args[2:])
	case "parse":
		parseCmd(os.Args[2:])
	case "version":
		fmt.Println("ail-go 0.1.0 (Go reference implementation)")
	case "-h", "--help", "help":
		usage()
	default:
		fmt.Fprintf(os.Stderr, "unknown command %q\n", os.Args[1])
		usage()
		os.Exit(2)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: ail-go <command> [args]")
	fmt.Fprintln(os.Stderr, "commands:")
	fmt.Fprintln(os.Stderr, "  run PROGRAM.ail [--input INPUT] [--model MODEL]")
	fmt.Fprintln(os.Stderr, "  parse PROGRAM.ail           # tokenize + parse; print ok/error")
	fmt.Fprintln(os.Stderr, "  version")
}

func runCmd(args []string) {
	// Accept the program path either before or after flags. Python's CLI
	// puts the path first (`ail run PROGRAM --input ...`); Go's flag
	// package stops scanning at the first non-flag, so we shuffle
	// positional args to the tail before calling Parse.
	path, rest := extractPositional(args)
	if path == "" {
		fmt.Fprintln(os.Stderr, "run: missing program path")
		os.Exit(2)
	}
	fs := flag.NewFlagSet("run", flag.ExitOnError)
	inputFlag := fs.String("input", "", "input for the entry parameter")
	modelFlag := fs.String("model", "", "ollama model for intent dispatch (or set AIL_OLLAMA_MODEL)")
	fs.Parse(rest)
	src, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read %s: %v\n", path, err)
		os.Exit(1)
	}
	lex := NewLexer(string(src))
	tokens, err := lex.Tokenize()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	prog, err := NewParser(tokens).ParseProgram()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var adapter Adapter
	if len(prog.Intents) > 0 {
		a := NewOllamaAdapter()
		if *modelFlag != "" {
			a.Model = *modelFlag
		}
		adapter = a
	}
	ev := NewEvaluator(prog, adapter)
	val, err := ev.Run(*inputFlag)
	if err != nil {
		fmt.Fprintln(os.Stderr, "runtime error:", err)
		os.Exit(1)
	}
	fmt.Println(toText(val.V))
}

// extractPositional returns the first non-flag argument and the remaining
// args (flags, plus any trailing positionals). Works whether the user
// passed `run PROGRAM --input ...` or `run --input ... PROGRAM`.
func extractPositional(args []string) (string, []string) {
	for i, a := range args {
		if len(a) == 0 || a[0] == '-' {
			continue
		}
		// skip the value of a previous flag like `--input 15`
		if i > 0 && args[i-1] != "" && args[i-1][0] == '-' && !isKnownBoolFlag(args[i-1]) {
			continue
		}
		rest := append([]string{}, args[:i]...)
		rest = append(rest, args[i+1:]...)
		return a, rest
	}
	return "", args
}

func isKnownBoolFlag(s string) bool {
	// No bool flags yet — every --flag consumes the next arg.
	return false
}

func parseCmd(args []string) {
	if len(args) < 1 {
		fmt.Fprintln(os.Stderr, "parse: missing program path")
		os.Exit(2)
	}
	src, err := os.ReadFile(args[0])
	if err != nil {
		fmt.Fprintf(os.Stderr, "read %s: %v\n", args[0], err)
		os.Exit(1)
	}
	tokens, err := NewLexer(string(src)).Tokenize()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	prog, err := NewParser(tokens).ParseProgram()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("parse ok: %d fn, %d intent, entry=%v\n", len(prog.Fns), len(prog.Intents), prog.Entry != nil)
}
