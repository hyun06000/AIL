//! AIL 파서 골격 — gil 사이클 ail-grammar-skeleton/parser-skeleton.
//! HEAAL 강제의 첫 실물: goal·done·never 없는 task, while 은 파싱되지 않는다.

pub mod lexer;
pub mod parser;

pub use parser::{parse_program, ParseOutcome};
