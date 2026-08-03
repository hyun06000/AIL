//! AIL 파서 + 인터프리터 — gil 체인 ail-runtime.
//! HEAAL 강제의 실물: goal·done·never 없는 task, while 은 파싱되지 않는다.
//! 그리고 실행 시점에 done 판정·never 차단·limit 예산이 작동한다.

pub mod lexer;
pub mod ast;
pub mod parser;
pub mod interp;

pub use parser::{parse, parse_program, ParseOutcome};
pub use ast::*;
pub use interp::{Interp, Value, RunOutcome};
