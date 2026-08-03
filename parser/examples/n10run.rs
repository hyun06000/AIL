use ail_parser::{parse, Interp, Value};
fn s(x:&str)->Value{Value::Str(x.into())}
fn n(x:f64)->Value{Value::Num(x)}
fn l(v:Vec<Value>)->Value{Value::List(v)}
fn o(kv:Vec<(&str,Value)>)->Value{
    let mut m=std::collections::BTreeMap::new();
    for (k,v) in kv { m.insert(k.to_string(), v); } Value::Obj(m)
}
fn main() {
    // 실행 가능한(파싱 통과) 문제에 입력을 고정한다. 효과 문제(P1·P9)는 제외.
    let cases: Vec<(&str, Vec<Value>)> = vec![
        ("P3", vec![l(vec![s("j1"), s("j2"), s("j3")])]),
        ("P5", vec![s("a b a c a b")]),
        ("P6", vec![o(vec![("name", s("srv")), ("port", n(8080.0)), ("mode", s("dev"))])]),
        ("P7", vec![l(vec![l(vec![n(1.0), n(2.0)]), l(vec![n(3.0), n(10.0)])])]),
        ("P8", vec![l(vec![
            o(vec![("name", s("a")), ("age", n(20.0)), ("active", Value::Bool(true))]),
            o(vec![("name", s("b")), ("age", n(15.0)), ("active", Value::Bool(true))]),
        ])]),
    ];
    for (tag, args) in cases {
        let path = format!("../experiments/scale/{}-ail.txt", tag);
        let src = match std::fs::read_to_string(&path) { Ok(x)=>x, Err(_)=>{ println!("{}: 파일 없음", tag); continue } };
        let p = match parse(&src) { Ok(p)=>p, Err(e)=>{ println!("{}: 파싱 실패 — {}", tag, e); continue } };
        let name = match p.items.first() {
            Some(ail_parser::Item::Task(t)) => t.name.clone(),
            Some(ail_parser::Item::Fn(f)) => f.name.clone(),
            None => { println!("{}: 항목 없음", tag); continue }
        };
        let is_task = matches!(p.items.first(), Some(ail_parser::Item::Task(_)));
        let mut it = Interp::new(&p);
        let r = if is_task { it.run_task(&name, args) } else { it.run_fn(&name, args) };
        match r {
            Ok(out) => println!("{}: {} {}", tag, out.value.show(),
                out.done_ok.map(|b| format!("(done={})", b)).unwrap_or_default()),
            Err(e) => println!("{}: 실행 오류 — {}", tag, e),
        }
    }
}
