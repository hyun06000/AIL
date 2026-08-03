//! HEAAL 강제 테스트 — "그 잘못을 표현/실행할 수 있는가"에 대한 답.
use ail_parser::parse_program;

const VALID: &str = r#"
task fetchUser(url) {
  goal load the user profile
  done profile.name != none
  never [fs, shell]
  limit 2000 tokens, 5 s
  uses [http]
  again 3 wait 2
  let data = http.get(url, timeout 5)
  return { ok true, name data.name }
  fail return { ok false, error }
}
"#;

#[test]
fn accepts_valid_contract() {
    let o = parse_program(VALID).expect("유효 계약은 통과해야 한다");
    assert_eq!(o.tasks, 1);
}

#[test]
fn rejects_missing_goal() {
    let src = VALID.replace("goal load the user profile\n", "");
    let e = parse_program(&src).unwrap_err();
    assert!(e.contains("goal"), "{}", e);
}

#[test]
fn rejects_missing_done() {
    let src = VALID.replace("done profile.name != none\n", "");
    let e = parse_program(&src).unwrap_err();
    assert!(e.contains("done"), "{}", e);
}

#[test]
fn rejects_missing_never() {
    let src = VALID.replace("never [fs, shell]\n", "");
    let e = parse_program(&src).unwrap_err();
    assert!(e.contains("never"), "{}", e);
}

#[test]
fn rejects_while() {
    let src = VALID.replace("again 3 wait 2", "while true { }");
    let e = parse_program(&src).unwrap_err();
    assert!(e.contains("while"), "{}", e);
}

#[test]
fn accepts_each_loop() {
    let src = r#"
task sum(xs) {
  goal add them
  done total >= 0
  never []
  let total = 0
  each x in xs { let total = total + x }
  return total
}
"#;
    parse_program(src).expect("each 는 성립해야 한다");
}

#[test]
fn accepts_reserved_bareword_key() {
    let src = r#"
task counts(jobs) {
  goal count
  done true
  never []
  return { done 5, fail 1 }
}
"#;
    parse_program(src).expect("예약어 bareword 키는 성립해야 한다 (v2 승인)");
}

#[test]
fn rejects_unbounded_again() {
    let src = VALID.replace("again 3 wait 2", "again forever");
    let e = parse_program(&src).unwrap_err();
    assert!(e.contains("again"), "{}", e);
}

// ── 6차 인터뷰 결정 반영 테스트 (D2·D4·D8) ──

#[test]
fn d8_reserved_word_as_variable() {
    let src = r#"
task counts(jobs) {
  goal count them
  done total >= 0
  never []
  let done = 0
  let total = done + 1
  return { done done }
}
"#;
    parse_program(src).expect("행 선두가 아닌 done 은 식별자다 (D8, 사람 확정)");
}

#[test]
fn d4_set_assignment_accepted() {
    let src = r#"
task acc(xs) {
  goal accumulate
  done total >= 0
  never []
  let total = 0
  each x in xs { set total = total + x }
  return total
}
"#;
    parse_program(src).expect("set 대입은 성립해야 한다 (D4)");
}

#[test]
fn d4_bare_assignment_rejected() {
    let src = r#"
task acc(xs) {
  goal accumulate
  done total >= 0
  never []
  let total = 0
  each x in xs { total = total + x }
  return total
}
"#;
    let e = parse_program(src).unwrap_err();
    assert!(e.contains("set"), "{}", e);
}

#[test]
fn d2_string_done_rejected() {
    let src = r#"
task f(x) {
  goal do it
  done "everything worked out"
  never []
  return x
}
"#;
    let e = parse_program(src).unwrap_err();
    assert!(e.contains("판정"), "{}", e);
}

// ── 순수 함수 fn (사이클 pure-fn 초안) ──

#[test]
fn pure_fn_accepted() {
    let src = r#"
fn mergeSorted(a, b) {
  let out = []
  each x in a { set out = push(out, x) }
  each y in b { set out = insertSorted(out, y) }
  return { list out, length len(out) }
}
"#;
    parse_program(src).expect("순수 fn 은 슬롯 없이 성립해야 한다");
}

#[test]
fn pure_fn_rejects_uses() {
    let src = "fn f(x) {\n  uses [http]\n  return x\n}\n";
    let e = parse_program(src).unwrap_err();
    assert!(e.contains("순수"), "{}", e);
}

#[test]
fn pure_fn_rejects_effect_call() {
    let src = "fn f(url) {\n  let r = http.get(url)\n  return r\n}\n";
    let e = parse_program(src).unwrap_err();
    assert!(e.contains("순수"), "{}", e);
}

#[test]
fn task_rules_unchanged_with_fn_present() {
    let src = r#"
fn add(a, b) { return a + b }
task main(xs) {
  goal add them all
  done total >= 0
  never []
  let total = 0
  each x in xs { set total = add(total, x) }
  return total
}
"#;
    parse_program(src).expect("fn 과 task 공존");
}
