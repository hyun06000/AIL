//! 정답성 시험 — Haiku 가 쓴 v9A 생성물을 **실제 입력으로 돌려** 기대 출력과 대조한다.
//!
//! 사이클 ail-runtime/interp-skeleton s2 의 핵심 물음:
//! 지난 세 체인은 "짧다"만 재었다. "맞다"는 한 번도 확인되지 않았다.
//! 틀린 답이 나오면 그대로 기록한다 — 그것이 이 사이클의 가장 값진 발견이다.

use ail_parser::{parse, Interp, Value};
use std::collections::BTreeMap;

fn src(path: &str) -> String {
    std::fs::read_to_string(format!("{}/../experiments/scale/{}", env!("CARGO_MANIFEST_DIR"), path))
        .unwrap_or_else(|e| panic!("생성물을 읽을 수 없다 {}: {}", path, e))
}

fn n(x: f64) -> Value { Value::Num(x) }
fn s(x: &str) -> Value { Value::Str(x.into()) }
fn l(v: Vec<Value>) -> Value { Value::List(v) }

/// 프로그램의 첫 fn 을 인자와 함께 돌린다 (생성물마다 이름이 달라서)
fn run_first(source: &str, args: Vec<Value>) -> Result<Value, String> {
    let p = parse(source)?;
    let name = p.items.iter().find_map(|i| match i {
        ail_parser::Item::Fn(f) => Some(f.name.clone()),
        _ => None,
    }).ok_or("fn 이 없다")?;
    let mut it = Interp::new(&p);
    it.run_fn(&name, args).map(|o| o.value)
}

fn obj(v: &Value) -> &BTreeMap<String, Value> {
    match v { Value::Obj(o) => o, other => panic!("객체를 기대했으나 {}", other.show()) }
}

// ── P4: 정렬된 두 리스트 병합 ──
#[test]
fn p4_merge_sorted_lists() {
    let out = run_first(&src("P4-ail-v9A.txt"), vec![
        l(vec![n(1.0), n(3.0), n(5.0)]),
        l(vec![n(2.0), n(4.0), n(6.0)]),
    ]).expect("P4 실행");
    let o = obj(&out);
    let merged = o.values().find(|v| matches!(v, Value::List(_))).expect("병합 리스트");
    assert_eq!(*merged, l(vec![n(1.0), n(2.0), n(3.0), n(4.0), n(5.0), n(6.0)]),
        "P4 병합 결과가 정렬되어야 한다");
    let len = o.values().find(|v| matches!(v, Value::Num(_))).expect("길이");
    assert_eq!(*len, n(6.0), "P4 길이");
}

// ── P5: 단어 빈도 상위 3 ──
#[test]
fn p5_top3_word_frequency() {
    // "a b a c a b" → a:3, b:2, c:1
    let out = run_first(&src("P5x-ail-v9A.txt"), vec![s("a b a c a b")]).expect("P5 실행");
    let list = match &out { Value::List(v) => v.clone(), other => panic!("리스트 기대: {}", other.show()) };
    assert_eq!(list.len(), 3, "상위 3개여야 한다");
    // 첫 항목이 최빈어 a(3회)여야 한다
    let first = &list[0];
    let fo = obj(first);
    let word = fo.values().find(|v| matches!(v, Value::Str(_))).expect("단어");
    let cnt = fo.values().find(|v| matches!(v, Value::Num(_))).expect("횟수");
    assert_eq!(*word, s("a"), "최빈어는 a");
    assert_eq!(*cnt, n(3.0), "a 는 3회");
}

// ── P7: 중첩 리스트 합계·개수·최대 ──
#[test]
fn p7_nested_sum_count_max() {
    let out = run_first(&src("P7-ail-v9A.txt"), vec![
        l(vec![
            l(vec![n(1.0), n(2.0)]),
            l(vec![n(3.0), n(10.0)]),
        ]),
    ]).expect("P7 실행");
    let o = obj(&out);
    let nums: Vec<f64> = o.values().filter_map(|v| match v { Value::Num(x) => Some(*x), _ => None }).collect();
    assert!(nums.contains(&16.0), "합계 16 이 있어야 한다: {:?}", nums);
    assert!(nums.contains(&4.0), "개수 4 가 있어야 한다: {:?}", nums);
    assert!(nums.contains(&10.0), "최대 10 이 있어야 한다: {:?}", nums);
}

// ── P10: 쿼리 문자열 파싱 ──
#[test]
fn p10_parse_query_string() {
    let out = run_first(&src("P10x-ail-v9A.txt"), vec![s("a=1&b=hello&c=")]).expect("P10 실행");
    let o = obj(&out);
    // 빈 값 개수 1
    let empty = o.values().find(|v| matches!(v, Value::Num(_))).expect("빈 값 개수");
    assert_eq!(*empty, n(1.0), "빈 값은 c 하나");
    // 파싱된 객체에 a=1, b=hello
    let parsed = o.values().find(|v| matches!(v, Value::Obj(_))).expect("파싱 객체");
    let po = obj(parsed);
    assert_eq!(po.get("a"), Some(&s("1")), "a=1");
    assert_eq!(po.get("b"), Some(&s("hello")), "b=hello");
}
