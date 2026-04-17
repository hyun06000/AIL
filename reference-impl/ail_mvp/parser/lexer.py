"""Tokenizer for AIL source.

Minimal, line-tracking lexer sufficient for the MVP grammar. Whitespace
is not significant; braces delimit blocks; colons introduce fields.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto


class Tok(Enum):
    # Literals
    IDENT = auto()
    STRING = auto()
    NUMBER = auto()

    # Punctuation
    LBRACE = auto()     # {
    RBRACE = auto()     # }
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    LBRACK = auto()     # [
    RBRACK = auto()     # ]
    COMMA = auto()
    COLON = auto()
    DOT = auto()
    ARROW = auto()      # ->
    FATARROW = auto()   # =>
    EQ = auto()         # =
    EQEQ = auto()       # ==
    NEQ = auto()        # !=
    LT = auto()
    GT = auto()
    LEQ = auto()
    GEQ = auto()
    GGT = auto()        # >>
    GGGT = auto()       # >>>
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()    # %

    # Structural
    NEWLINE = auto()
    EOF = auto()


KEYWORDS = {
    "intent", "context", "evolve", "effect", "entry", "import", "from", "as",
    "goal", "constraints", "examples", "on_low_confidence", "trace",
    "with", "override", "extends", "perform", "branch", "otherwise",
    "prefer", "require", "when", "calibrate_on", "rollback_on",
    "metric", "history", "keep_last", "under", "matching",
    "and", "or", "not", "in", "such", "that",
    "return", "true", "false", "threshold",
    "fn", "pure", "if", "else", "for",
}


@dataclass
class Token:
    kind: Tok
    value: str
    line: int
    col: int

    def __repr__(self) -> str:
        return f"{self.kind.name}({self.value!r})@{self.line}:{self.col}"


class LexError(Exception):
    pass


class Lexer:
    def __init__(self, source: str):
        self.src = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: list[Token] = []

    def error(self, msg: str) -> None:
        raise LexError(f"{self.line}:{self.col}: {msg}")

    def peek(self, offset: int = 0) -> str:
        p = self.pos + offset
        return self.src[p] if p < len(self.src) else ""

    def advance(self) -> str:
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def add(self, kind: Tok, value: str, line: int, col: int) -> None:
        self.tokens.append(Token(kind, value, line, col))

    def tokenize(self) -> list[Token]:
        while self.pos < len(self.src):
            ch = self.peek()
            # Skip whitespace (newlines are insignificant in MVP)
            if ch in " \t\r\n":
                self.advance()
                continue
            # Comments: // to end of line, /* */ block
            if ch == "/" and self.peek(1) == "/":
                while self.pos < len(self.src) and self.peek() != "\n":
                    self.advance()
                continue
            if ch == "/" and self.peek(1) == "*":
                self.advance(); self.advance()
                while self.pos < len(self.src) and not (self.peek() == "*" and self.peek(1) == "/"):
                    self.advance()
                if self.pos < len(self.src):
                    self.advance(); self.advance()
                continue
            # Strings
            if ch == '"':
                self._lex_string()
                continue
            # Numbers
            if ch.isdigit():
                self._lex_number()
                continue
            # Identifiers / keywords
            if ch.isalpha() or ch == "_":
                self._lex_identifier()
                continue
            # Punctuation / operators
            self._lex_punct()
        self.add(Tok.EOF, "", self.line, self.col)
        return self.tokens

    def _lex_string(self) -> None:
        line, col = self.line, self.col
        self.advance()  # opening "
        buf = []
        while self.pos < len(self.src) and self.peek() != '"':
            ch = self.advance()
            if ch == "\\" and self.pos < len(self.src):
                nxt = self.advance()
                esc = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"'}
                buf.append(esc.get(nxt, nxt))
            else:
                buf.append(ch)
        if self.pos >= len(self.src):
            self.error("unterminated string")
        self.advance()  # closing "
        self.add(Tok.STRING, "".join(buf), line, col)

    def _lex_number(self) -> None:
        line, col = self.line, self.col
        start = self.pos
        while self.pos < len(self.src) and (self.peek().isdigit() or self.peek() == "."):
            self.advance()
        # Allow suffixes like 'ms', 's' for durations: attach as IDENT separately
        value = self.src[start:self.pos]
        self.add(Tok.NUMBER, value, line, col)

    def _lex_identifier(self) -> None:
        line, col = self.line, self.col
        start = self.pos
        while self.pos < len(self.src) and (self.peek().isalnum() or self.peek() == "_"):
            self.advance()
        value = self.src[start:self.pos]
        self.add(Tok.IDENT, value, line, col)

    def _lex_punct(self) -> None:
        line, col = self.line, self.col
        ch = self.advance()
        two = ch + (self.peek() if self.pos < len(self.src) else "")
        three = two + (self.peek(1) if self.pos + 1 < len(self.src) else "")

        if three == ">>>":
            self.advance(); self.advance()
            self.add(Tok.GGGT, ">>>", line, col); return
        if two == "->":
            self.advance(); self.add(Tok.ARROW, "->", line, col); return
        if two == "=>":
            self.advance(); self.add(Tok.FATARROW, "=>", line, col); return
        if two == "==":
            self.advance(); self.add(Tok.EQEQ, "==", line, col); return
        if two == "!=":
            self.advance(); self.add(Tok.NEQ, "!=", line, col); return
        if two == "<=":
            self.advance(); self.add(Tok.LEQ, "<=", line, col); return
        if two == ">=":
            self.advance(); self.add(Tok.GEQ, ">=", line, col); return
        if two == ">>":
            self.advance(); self.add(Tok.GGT, ">>", line, col); return

        single = {
            "{": Tok.LBRACE, "}": Tok.RBRACE,
            "(": Tok.LPAREN, ")": Tok.RPAREN,
            "[": Tok.LBRACK, "]": Tok.RBRACK,
            ",": Tok.COMMA, ":": Tok.COLON, ".": Tok.DOT,
            "=": Tok.EQ, "<": Tok.LT, ">": Tok.GT,
            "+": Tok.PLUS, "-": Tok.MINUS, "*": Tok.STAR, "/": Tok.SLASH,
            "%": Tok.PERCENT,
        }
        if ch in single:
            self.add(single[ch], ch, line, col); return
        self.error(f"unexpected character {ch!r}")


def tokenize(source: str) -> list[Token]:
    return Lexer(source).tokenize()
