package main

import (
	"fmt"
	"strings"
	"unicode"
)

// TokKind enumerates the token types the AIL lexer produces. Keep this in
// sync with the Python reference implementation (reference-impl/ail_mvp/
// parser/lexer.py) — the tokens are the language, not an implementation
// detail.
type TokKind int

const (
	TokEOF TokKind = iota
	TokIdent
	TokNumber
	TokString
	TokLBrace
	TokRBrace
	TokLParen
	TokRParen
	TokLBrack
	TokRBrack
	TokComma
	TokColon
	TokDot
	TokArrow    // ->
	TokFatArrow // =>
	TokEq       // =
	TokEqEq     // ==
	TokNeq      // !=
	TokLT
	TokGT
	TokLEQ
	TokGEQ
	TokPlus
	TokMinus
	TokStar
	TokSlash
	TokPercent
)

type Token struct {
	Kind  TokKind
	Value string
	Line  int
	Col   int
}

func (t Token) String() string {
	return fmt.Sprintf("%s(%q)@%d:%d", tokName(t.Kind), t.Value, t.Line, t.Col)
}

func tokName(k TokKind) string {
	switch k {
	case TokEOF:
		return "EOF"
	case TokIdent:
		return "IDENT"
	case TokNumber:
		return "NUMBER"
	case TokString:
		return "STRING"
	case TokLBrace:
		return "{"
	case TokRBrace:
		return "}"
	case TokLParen:
		return "("
	case TokRParen:
		return ")"
	case TokLBrack:
		return "["
	case TokRBrack:
		return "]"
	case TokComma:
		return ","
	case TokColon:
		return ":"
	case TokDot:
		return "."
	case TokArrow:
		return "->"
	case TokFatArrow:
		return "=>"
	case TokEq:
		return "="
	case TokEqEq:
		return "=="
	case TokNeq:
		return "!="
	case TokLT:
		return "<"
	case TokGT:
		return ">"
	case TokLEQ:
		return "<="
	case TokGEQ:
		return ">="
	case TokPlus:
		return "+"
	case TokMinus:
		return "-"
	case TokStar:
		return "*"
	case TokSlash:
		return "/"
	case TokPercent:
		return "%"
	}
	return fmt.Sprintf("tok<%d>", int(k))
}

type LexError struct {
	Line, Col int
	Msg       string
}

func (e LexError) Error() string { return fmt.Sprintf("lex error at %d:%d: %s", e.Line, e.Col, e.Msg) }

type Lexer struct {
	src  string
	pos  int
	line int
	col  int
}

func NewLexer(src string) *Lexer { return &Lexer{src: src, line: 1, col: 1} }

func (l *Lexer) peekAt(off int) byte {
	i := l.pos + off
	if i >= len(l.src) {
		return 0
	}
	return l.src[i]
}

func (l *Lexer) peek() byte { return l.peekAt(0) }

func (l *Lexer) advance() byte {
	ch := l.src[l.pos]
	l.pos++
	if ch == '\n' {
		l.line++
		l.col = 1
	} else {
		l.col++
	}
	return ch
}

// Tokenize consumes the entire source, returning the token stream terminated
// by TokEOF. Whitespace, // line comments, and /* block comments */ are
// skipped. Braces delimit blocks; colons introduce fields.
func (l *Lexer) Tokenize() ([]Token, error) {
	var out []Token
	for l.pos < len(l.src) {
		ch := l.peek()
		// whitespace
		if ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n' {
			l.advance()
			continue
		}
		// // line comment
		if ch == '/' && l.peekAt(1) == '/' {
			for l.pos < len(l.src) && l.peek() != '\n' {
				l.advance()
			}
			continue
		}
		// /* block comment */
		if ch == '/' && l.peekAt(1) == '*' {
			l.advance()
			l.advance()
			for l.pos < len(l.src) && !(l.peek() == '*' && l.peekAt(1) == '/') {
				l.advance()
			}
			if l.pos < len(l.src) {
				l.advance()
				l.advance()
			}
			continue
		}
		// strings
		if ch == '"' {
			tok, err := l.lexString()
			if err != nil {
				return nil, err
			}
			out = append(out, tok)
			continue
		}
		// numbers
		if ch >= '0' && ch <= '9' {
			out = append(out, l.lexNumber())
			continue
		}
		// identifiers / keywords
		if unicode.IsLetter(rune(ch)) || ch == '_' {
			out = append(out, l.lexIdent())
			continue
		}
		// punctuation / operators
		tok, err := l.lexPunct()
		if err != nil {
			return nil, err
		}
		out = append(out, tok)
	}
	out = append(out, Token{Kind: TokEOF, Line: l.line, Col: l.col})
	return out, nil
}

func (l *Lexer) lexString() (Token, error) {
	line, col := l.line, l.col
	l.advance() // opening "
	var b strings.Builder
	for l.pos < len(l.src) && l.peek() != '"' {
		ch := l.advance()
		if ch == '\\' && l.pos < len(l.src) {
			nxt := l.advance()
			switch nxt {
			case 'n':
				b.WriteByte('\n')
			case 't':
				b.WriteByte('\t')
			case 'r':
				b.WriteByte('\r')
			case '\\':
				b.WriteByte('\\')
			case '"':
				b.WriteByte('"')
			default:
				b.WriteByte(nxt)
			}
		} else {
			b.WriteByte(ch)
		}
	}
	if l.pos >= len(l.src) {
		return Token{}, LexError{l.line, l.col, "unterminated string"}
	}
	l.advance() // closing "
	return Token{Kind: TokString, Value: b.String(), Line: line, Col: col}, nil
}

func (l *Lexer) lexNumber() Token {
	line, col := l.line, l.col
	start := l.pos
	for l.pos < len(l.src) && (isDigit(l.peek()) || l.peek() == '.') {
		l.advance()
	}
	return Token{Kind: TokNumber, Value: l.src[start:l.pos], Line: line, Col: col}
}

func (l *Lexer) lexIdent() Token {
	line, col := l.line, l.col
	start := l.pos
	for l.pos < len(l.src) {
		ch := l.peek()
		if !(unicode.IsLetter(rune(ch)) || isDigit(ch) || ch == '_') {
			break
		}
		l.advance()
	}
	return Token{Kind: TokIdent, Value: l.src[start:l.pos], Line: line, Col: col}
}

func (l *Lexer) lexPunct() (Token, error) {
	line, col := l.line, l.col
	ch := l.advance()
	next := byte(0)
	if l.pos < len(l.src) {
		next = l.peek()
	}
	two := string([]byte{ch, next})
	switch two {
	case "->":
		l.advance()
		return Token{Kind: TokArrow, Value: two, Line: line, Col: col}, nil
	case "=>":
		l.advance()
		return Token{Kind: TokFatArrow, Value: two, Line: line, Col: col}, nil
	case "==":
		l.advance()
		return Token{Kind: TokEqEq, Value: two, Line: line, Col: col}, nil
	case "!=":
		l.advance()
		return Token{Kind: TokNeq, Value: two, Line: line, Col: col}, nil
	case "<=":
		l.advance()
		return Token{Kind: TokLEQ, Value: two, Line: line, Col: col}, nil
	case ">=":
		l.advance()
		return Token{Kind: TokGEQ, Value: two, Line: line, Col: col}, nil
	}
	switch ch {
	case '{':
		return Token{Kind: TokLBrace, Value: "{", Line: line, Col: col}, nil
	case '}':
		return Token{Kind: TokRBrace, Value: "}", Line: line, Col: col}, nil
	case '(':
		return Token{Kind: TokLParen, Value: "(", Line: line, Col: col}, nil
	case ')':
		return Token{Kind: TokRParen, Value: ")", Line: line, Col: col}, nil
	case '[':
		return Token{Kind: TokLBrack, Value: "[", Line: line, Col: col}, nil
	case ']':
		return Token{Kind: TokRBrack, Value: "]", Line: line, Col: col}, nil
	case ',':
		return Token{Kind: TokComma, Value: ",", Line: line, Col: col}, nil
	case ':':
		return Token{Kind: TokColon, Value: ":", Line: line, Col: col}, nil
	case '.':
		return Token{Kind: TokDot, Value: ".", Line: line, Col: col}, nil
	case '=':
		return Token{Kind: TokEq, Value: "=", Line: line, Col: col}, nil
	case '<':
		return Token{Kind: TokLT, Value: "<", Line: line, Col: col}, nil
	case '>':
		return Token{Kind: TokGT, Value: ">", Line: line, Col: col}, nil
	case '+':
		return Token{Kind: TokPlus, Value: "+", Line: line, Col: col}, nil
	case '-':
		return Token{Kind: TokMinus, Value: "-", Line: line, Col: col}, nil
	case '*':
		return Token{Kind: TokStar, Value: "*", Line: line, Col: col}, nil
	case '/':
		return Token{Kind: TokSlash, Value: "/", Line: line, Col: col}, nil
	case '%':
		return Token{Kind: TokPercent, Value: "%", Line: line, Col: col}, nil
	}
	return Token{}, LexError{line, col, fmt.Sprintf("unexpected character %q", ch)}
}

func isDigit(ch byte) bool { return ch >= '0' && ch <= '9' }
