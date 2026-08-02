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
