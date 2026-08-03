use ail_parser::{parse, parse_program};
fn main() {
    // scale-experiment(N=10, 카드 v3) 생성물 — 당시 ail-check 10/10 을 주장했다
    for i in 1..=10 {
        let path = format!("../experiments/scale/P{}-ail.txt", i);
        let src = match std::fs::read_to_string(&path) { Ok(s) => s, Err(_) => { println!("P{}: 파일 없음", i); continue } };
        match parse_program(&src) {
            Ok(o) => {
                let items = parse(&src).map(|p| {
                    let f = p.items.iter().filter(|x| matches!(x, ail_parser::Item::Fn(_))).count();
                    let t = p.items.len() - f;
                    format!("fn {} · task {}", f, t)
                }).unwrap_or_default();
                println!("P{}: 파싱 OK ({}) {}", i, items, if o.warnings.is_empty() { String::new() } else { format!("경고 {}", o.warnings.len()) });
            }
            Err(e) => println!("P{}: REJECT — {}", i, e),
        }
    }
}
