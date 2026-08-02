use std::{env, fs, process};

fn main() {
    let path = env::args().nth(1).unwrap_or_else(|| {
        eprintln!("사용: ail-check <파일.ail>");
        process::exit(2);
    });
    let src = fs::read_to_string(&path).unwrap_or_else(|e| {
        eprintln!("읽기 실패 {}: {}", path, e);
        process::exit(2);
    });
    match ail_parser::parse_program(&src) {
        Ok(o) => {
            println!("OK — task {}개", o.tasks);
            for w in o.warnings { println!("  ⚠ {}", w); }
        }
        Err(e) => {
            println!("REJECT — {}", e);
            process::exit(1);
        }
    }
}
