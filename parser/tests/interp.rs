//! 인터프리터 시험 — 사이클 ail-runtime/interp-skeleton s2.
//! 핵심: HEAAL 3강제(done·never·limit)가 **실행 시점에** 작동하는가.

use ail_parser::{parse, Interp, Value};

fn run_fn(src: &str, name: &str, args: Vec<Value>) -> Value {
    let p = parse(src).expect("파싱");
    let mut it = Interp::new(&p);
    it.run_fn(name, args).expect("실행").value
}

fn num(n: f64) -> Value { Value::Num(n) }
fn s(x: &str) -> Value { Value::Str(x.into()) }
fn list(v: Vec<Value>) -> Value { Value::List(v) }

// ── 기본 평가 ──

#[test]
fn fn_returns_arithmetic() {
    let v = run_fn("fn add(a, b) {\n  return a + b\n}\n", "add", vec![num(2.0), num(3.0)]);
    assert_eq!(v, num(5.0));
}

#[test]
fn each_accumulates() {
    let src = "fn total(xs) {\n  let t = 0\n  each x in xs {\n    set t = t + x\n  }\n  return t\n}\n";
    let v = run_fn(src, "total", vec![list(vec![num(1.0), num(2.0), num(3.0)])]);
    assert_eq!(v, num(6.0));
}

#[test]
fn each_with_index() {
    let src = "fn weighted(xs) {\n  let t = 0\n  each x, i in xs {\n    set t = t + x * i\n  }\n  return t\n}\n";
    let v = run_fn(src, "weighted", vec![list(vec![num(5.0), num(10.0), num(20.0)])]);
    assert_eq!(v, num(50.0)); // 5*0 + 10*1 + 20*2
}

#[test]
fn if_expression_evaluates() {
    let src = "fn pick(c) {\n  let y = if c > 0 { 10 } else { 20 }\n  return y\n}\n";
    assert_eq!(run_fn(src, "pick", vec![num(1.0)]), num(10.0));
    assert_eq!(run_fn(src, "pick", vec![num(-1.0)]), num(20.0));
}

// ── 조합자 8종 ──

#[test]
fn combinator_map_with_named_fn() {
    let src = "fn double(x) { return x * 2 }\nfn go(xs) { return map(xs, double) }\n";
    let v = run_fn(src, "go", vec![list(vec![num(1.0), num(2.0)])]);
    assert_eq!(v, list(vec![num(2.0), num(4.0)]));
}

#[test]
fn combinator_map_with_lambda() {
    let src = "fn go(xs) { return map(xs, x => x * 3) }\n";
    let v = run_fn(src, "go", vec![list(vec![num(1.0), num(2.0)])]);
    assert_eq!(v, list(vec![num(3.0), num(6.0)]));
}

#[test]
fn combinator_filter_sort_take() {
    let src = "fn go(xs) {\n  let big = filter(xs, x => x > 2)\n  let ordered = sort(big)\n  return take(ordered, 2)\n}\n";
    let v = run_fn(src, "go", vec![list(vec![num(5.0), num(1.0), num(3.0), num(9.0)])]);
    assert_eq!(v, list(vec![num(3.0), num(5.0)]));
}

#[test]
fn combinator_sort_by_key_descending() {
    // v9A 생성물이 실제로 쓰는 관용: 음수 키로 내림차순
    let src = "fn go(xs) { return sort(xs, x => 0 - x) }\n";
    let v = run_fn(src, "go", vec![list(vec![num(1.0), num(3.0), num(2.0)])]);
    assert_eq!(v, list(vec![num(3.0), num(2.0), num(1.0)]));
}

#[test]
fn combinator_count_and_group() {
    let src = "fn c(xs) { return count(xs) }\n";
    let v = run_fn(src, "c", vec![list(vec![s("a"), s("b"), s("a")])]);
    if let Value::Obj(o) = v {
        assert_eq!(o.get("a"), Some(&num(2.0)));
        assert_eq!(o.get("b"), Some(&num(1.0)));
    } else { panic!("count 는 객체를 낸다: {:?}", v); }
}

#[test]
fn combinator_reduce() {
    let src = "fn go(xs) { return reduce(xs, 0, add) }\nfn add(a, b) { return a + b }\n";
    let v = run_fn(src, "go", vec![list(vec![num(1.0), num(2.0), num(4.0)])]);
    assert_eq!(v, num(7.0));
}

// ── 저수준 내장 ──

#[test]
fn builtins_string_and_collection() {
    let src = "fn go(t) {\n  let ws = split(lower(trim(t)), \" \")\n  return len(ws)\n}\n";
    assert_eq!(run_fn(src, "go", vec![s("  A B C  ")]), num(3.0));
}

// ── HEAAL 강제: 실행 시점 ──

#[test]
fn heaal_done_false_is_not_success() {
    // done 이 거짓이면 성공이 아니다 (H3)
    let src = "task t(xs) {\n  goal sum them\n  done total > 100\n  never [fs]\n  let total = 0\n  each x in xs { set total = total + x }\n  return { total total }\n}\n";
    let p = parse(src).expect("파싱");
    let mut it = Interp::new(&p);
    let out = it.run_task("t", vec![list(vec![num(1.0), num(2.0)])]).expect("실행");
    assert_eq!(out.done_ok, Some(false), "총합 3 은 done(>100) 을 만족하지 않는다");
}

#[test]
fn heaal_done_true_when_satisfied() {
    let src = "task t(xs) {\n  goal sum them\n  done total > 100\n  never [fs]\n  let total = 0\n  each x in xs { set total = total + x }\n  return { total total }\n}\n";
    let p = parse(src).expect("파싱");
    let mut it = Interp::new(&p);
    let out = it.run_task("t", vec![list(vec![num(500.0)])]).expect("실행");
    assert_eq!(out.done_ok, Some(true));
}

#[test]
fn heaal_never_blocks_capability_at_runtime() {
    // never 에 오른 능력을 부르면 차단된다 (H1)
    let src = "task t(u) {\n  goal fetch\n  done ok\n  never [http]\n  uses [fs]\n  let r = http.get(u)\n  return { r r }\n}\n";
    let p = parse(src).expect("파싱");
    let mut it = Interp::new(&p);
    let e = it.run_task("t", vec![s("http://x")]).unwrap_err();
    assert!(e.contains("never"), "차단 메시지여야 한다: {}", e);
}

#[test]
fn heaal_limit_budget_stops_execution() {
    // limit ops 예산이 소진되면 중단된다 (H4 실행판)
    let src = "task t(xs) {\n  goal count\n  done n >= 0\n  never [fs]\n  limit 12 ops\n  let n = 0\n  each x in xs { set n = n + 1 }\n  return { n n }\n}\n";
    let p = parse(src).expect("파싱");
    let mut it = Interp::new(&p);
    let big: Vec<Value> = (0..50).map(|i| num(i as f64)).collect();
    let e = it.run_task("t", vec![list(big)]).unwrap_err();
    assert!(e.contains("limit"), "예산 소진 메시지여야 한다: {}", e);
}

#[test]
fn heaal_limit_absent_means_no_budget() {
    let src = "task t(xs) {\n  goal count\n  done n >= 0\n  never [fs]\n  let n = 0\n  each x in xs { set n = n + 1 }\n  return { n n }\n}\n";
    let p = parse(src).expect("파싱");
    let mut it = Interp::new(&p);
    let big: Vec<Value> = (0..50).map(|i| num(i as f64)).collect();
    let out = it.run_task("t", vec![list(big)]).expect("예산 없으면 끝까지 돈다");
    assert_eq!(out.done_ok, Some(true));
}
