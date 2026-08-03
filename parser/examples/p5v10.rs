use ail_parser::{parse, Interp, Value};
fn main() {
    for tag in ["P5x", "P5y", "P5z"] {
        let path = format!("../experiments/scale/{}-ail-v10A.txt", tag);
        let src = std::fs::read_to_string(&path).unwrap();
        let p = match parse(&src) { Ok(p) => p, Err(e) => { println!("{}: 파싱 실패 — {}", tag, e); continue } };
        let name = p.items.iter().find_map(|i| match i {
            ail_parser::Item::Fn(f) => Some(f.name.clone()), _ => None }).unwrap();
        let mut it = Interp::new(&p);
        match it.run_fn(&name, vec![Value::Str("a b a c a b".into())]) {
            Ok(o) => println!("{}: {}", tag, o.value.show()),
            Err(e) => println!("{}: 실행 오류 — {}", tag, e),
        }
    }
}
