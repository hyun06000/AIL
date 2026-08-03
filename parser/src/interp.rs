//! 트리워킹 인터프리터 — AIL 이 처음으로 **실행되는** 자리.
//!
//! 사이클 ail-runtime/interp-skeleton. 파서는 done·never·limit 이 문법적으로
//! 존재하는지만 본다. 여기서 그것들이 **작동한다**:
//!   · done   — task 본문 실행 후 식을 평가한다. false 면 성공이 아니다 (H3)
//!   · never  — 목록에 오른 능력을 호출하면 즉시 차단한다 (H1)
//!   · limit  — ops 예산을 세고 초과하면 중단한다 (H4 의 실행판)

use crate::ast::*;
use std::collections::BTreeMap;
use std::rc::Rc;

#[derive(Debug, Clone)]
pub enum Value {
    Num(f64),
    Str(String),
    Bool(bool),
    List(Vec<Value>),
    /// bareword 객체 — 키 순서를 보존해야 비교가 안정적이라 BTreeMap
    Obj(BTreeMap<String, Value>),
    Fn(Rc<FnDecl>),
    Lambda(String, Rc<Expr>, Rc<Env>),
    Nothing,
}

impl PartialEq for Value {
    fn eq(&self, other: &Self) -> bool {
        use Value::*;
        match (self, other) {
            (Num(a), Num(b)) => a == b,
            (Str(a), Str(b)) => a == b,
            (Bool(a), Bool(b)) => a == b,
            (List(a), List(b)) => a == b,
            (Obj(a), Obj(b)) => a == b,
            (Nothing, Nothing) => true,
            (Fn(a), Fn(b)) => a.name == b.name,
            _ => false, // 람다는 동일성 비교 대상이 아니다
        }
    }
}

impl Value {
    pub fn truthy(&self) -> bool {
        match self {
            Value::Bool(b) => *b,
            Value::Num(n) => *n != 0.0,
            Value::Str(s) => !s.is_empty(),
            Value::List(l) => !l.is_empty(),
            Value::Obj(o) => !o.is_empty(),
            Value::Nothing => false,
            _ => true,
        }
    }
    pub fn show(&self) -> String {
        match self {
            Value::Num(n) => if n.fract() == 0.0 { format!("{}", *n as i64) } else { format!("{}", n) },
            Value::Str(s) => format!("\"{}\"", s),
            Value::Bool(b) => b.to_string(),
            Value::List(l) => format!("[{}]", l.iter().map(|v| v.show()).collect::<Vec<_>>().join(", ")),
            Value::Obj(o) => format!("{{{}}}", o.iter().map(|(k, v)| format!("{} {}", k, v.show())).collect::<Vec<_>>().join(", ")),
            Value::Fn(f) => format!("<fn {}>", f.name),
            Value::Lambda(p, _, _) => format!("<lambda {}>", p),
            Value::Nothing => "none".into(),
        }
    }
}

/// 스코프 체인 — 부모를 타고 올라간다
#[derive(Debug, Default)]
pub struct Env {
    vars: std::cell::RefCell<BTreeMap<String, Value>>,
    parent: Option<Rc<Env>>,
}

impl Env {
    pub fn new() -> Rc<Env> { Rc::new(Env::default()) }
    pub fn child(parent: &Rc<Env>) -> Rc<Env> {
        Rc::new(Env { vars: Default::default(), parent: Some(parent.clone()) })
    }
    pub fn get(&self, k: &str) -> Option<Value> {
        if let Some(v) = self.vars.borrow().get(k) { return Some(v.clone()); }
        self.parent.as_ref().and_then(|p| p.get(k))
    }
    pub fn define(&self, k: &str, v: Value) { self.vars.borrow_mut().insert(k.into(), v); }
    /// 이미 있는 자리에 재대입(set). 없으면 현재 스코프에 만든다.
    pub fn assign(&self, k: &str, v: Value) {
        if self.vars.borrow().contains_key(k) { self.vars.borrow_mut().insert(k.into(), v); return; }
        if let Some(p) = &self.parent {
            if p.get(k).is_some() { p.assign(k, v); return; }
        }
        self.vars.borrow_mut().insert(k.into(), v);
    }
}

#[derive(Debug)]
pub enum Halt {
    /// `return e` — 값을 들고 나간다
    Return(Value),
    /// `fail return e`
    Fail(Value),
    /// 실행 오류 (never 차단·limit 초과 포함)
    Err(String),
}

pub type Exec<T> = Result<T, Halt>;

/// 실행 결과 — 지표 측정을 위해 ops 도 함께 낸다
#[derive(Debug)]
pub struct RunOutcome {
    pub value: Value,
    pub ops: u64,
    pub done_ok: Option<bool>,
    pub warnings: Vec<String>,
}

pub struct Interp<'a> {
    prog: &'a Program,
    /// never 목록 — 이 능력의 호출은 차단된다 (H1)
    blocked: Vec<String>,
    ops: u64,
    /// limit ops 예산 (H4 실행판)
    budget: Option<u64>,
}

const EFFECT_NS: [&str; 7] = ["http", "fs", "shell", "state", "env", "llm", "clock"];

impl<'a> Interp<'a> {
    pub fn new(prog: &'a Program) -> Self {
        Interp { prog, blocked: Vec::new(), ops: 0, budget: None }
    }

    fn tick(&mut self) -> Exec<()> {
        self.ops += 1;
        if let Some(b) = self.budget {
            if self.ops > b {
                return Err(Halt::Err(format!("limit 예산 소진 — {} ops 를 넘었다 (H4: 예산은 선언이 아니라 강제다)", b)));
            }
        }
        Ok(())
    }

    /// fn 하나를 인자와 함께 실행한다 (순수 계산 경로)
    pub fn run_fn(&mut self, name: &str, args: Vec<Value>) -> Result<RunOutcome, String> {
        let f = self.prog.find_fn(name).ok_or_else(|| format!("fn `{}` 이 없다", name))?;
        let env = Env::new();
        self.bind_globals(&env);
        let fenv = Env::child(&env);
        for (p, a) in f.params.iter().zip(args) { fenv.define(p, a); }
        let body = f.body.clone();
        let v = match self.exec_block(&body, &fenv) {
            Ok(()) => Value::Nothing,
            Err(Halt::Return(v)) => v,
            Err(Halt::Fail(v)) => v,
            Err(Halt::Err(e)) => return Err(e),
        };
        Ok(RunOutcome { value: v, ops: self.ops, done_ok: None, warnings: vec![] })
    }

    /// task 실행 — 3슬롯이 실제로 작동한다
    pub fn run_task(&mut self, name: &str, args: Vec<Value>) -> Result<RunOutcome, String> {
        let t = self.prog.find_task(name).ok_or_else(|| format!("task `{}` 이 없다", name))?.clone();
        self.blocked = t.never.clone();
        self.budget = parse_ops_budget(t.limit.as_deref());
        let env = Env::new();
        self.bind_globals(&env);
        let tenv = Env::child(&env);
        for (p, a) in t.params.iter().zip(args) { tenv.define(p, a); }
        let v = match self.exec_block(&t.body, &tenv) {
            Ok(()) => Value::Nothing,
            Err(Halt::Return(v)) => v,
            Err(Halt::Fail(v)) => v,
            Err(Halt::Err(e)) => return Err(e),
        };
        // ── done 판정 (H3: 결정론적 식이지 LLM 이 아니다) ──
        let done_ok = match &t.done {
            Some(e) => {
                // 반환값의 필드를 done 식에서 참조할 수 있게 스코프에 얹는다
                if let Value::Obj(o) = &v {
                    for (k, val) in o { tenv.define(k, val.clone()); }
                }
                match self.eval(e, &tenv) {
                    Ok(dv) => Some(dv.truthy()),
                    Err(Halt::Err(e)) => return Err(e),
                    Err(_) => None,
                }
            }
            None => None,
        };
        Ok(RunOutcome { value: v, ops: self.ops, done_ok, warnings: vec![] })
    }

    fn bind_globals(&self, env: &Rc<Env>) {
        for item in &self.prog.items {
            if let Item::Fn(f) = item {
                env.define(&f.name, Value::Fn(Rc::new(f.clone())));
            }
        }
    }

    fn exec_block(&mut self, b: &[Stmt], env: &Rc<Env>) -> Exec<()> {
        for s in b { self.exec(s, env)?; }
        Ok(())
    }

    fn exec(&mut self, s: &Stmt, env: &Rc<Env>) -> Exec<()> {
        self.tick()?;
        match s {
            Stmt::Let(t, e) | Stmt::Set(t, e) => {
                let v = self.eval(e, env)?;
                if t.path.is_empty() {
                    match s {
                        Stmt::Let(..) => env.define(&t.name, v),
                        _ => env.assign(&t.name, v),
                    }
                } else {
                    let base = env.get(&t.name).unwrap_or(Value::Obj(BTreeMap::new()));
                    let updated = self.assign_path(base, &t.path, v, env)?;
                    env.assign(&t.name, updated);
                }
                Ok(())
            }
            Stmt::Each { var, idx, iter, body } => {
                let it = self.eval(iter, env)?;
                let items: Vec<Value> = match it {
                    Value::List(l) => l,
                    Value::Obj(o) => o.keys().map(|k| Value::Str(k.clone())).collect(),
                    Value::Str(s) => s.chars().map(|c| Value::Str(c.to_string())).collect(),
                    other => return Err(Halt::Err(format!("each 는 유한 컬렉션 위에서만 돈다 (H4) — 받은 것 {}", other.show()))),
                };
                for (i, item) in items.into_iter().enumerate() {
                    let benv = Env::child(env);
                    benv.define(var, item);
                    if let Some(ix) = idx { benv.define(ix, Value::Num(i as f64)); }
                    self.exec_block(body, &benv)?;
                }
                Ok(())
            }
            Stmt::If { cond, then, els } => {
                if self.eval(cond, env)?.truthy() {
                    self.exec_block(then, &Env::child(env))
                } else if let Some(e) = els {
                    self.exec_block(e, &Env::child(env))
                } else { Ok(()) }
            }
            Stmt::Match { subject, cases } => {
                let sv = self.eval(subject, env)?;
                for (pat, body) in cases {
                    let pv = self.eval(pat, env)?;
                    if pv == sv { return self.exec_block(body, &Env::child(env)); }
                }
                Ok(())
            }
            Stmt::Return(e) => {
                let v = match e { Some(x) => self.eval(x, env)?, None => Value::Nothing };
                Err(Halt::Return(v))
            }
            Stmt::FailReturn(e) => {
                let v = match e { Some(x) => self.eval(x, env)?, None => Value::Nothing };
                Err(Halt::Fail(v))
            }
            Stmt::Expr(e) => { self.eval(e, env)?; Ok(()) }
        }
    }

    fn assign_path(&mut self, base: Value, path: &[PathSeg], v: Value, env: &Rc<Env>) -> Exec<Value> {
        if path.is_empty() { return Ok(v); }
        match (&path[0], base) {
            (PathSeg::Member(k), Value::Obj(mut o)) => {
                let inner = o.get(k).cloned().unwrap_or(Value::Obj(BTreeMap::new()));
                let nv = self.assign_path(inner, &path[1..], v, env)?;
                o.insert(k.clone(), nv);
                Ok(Value::Obj(o))
            }
            (PathSeg::Index(ie), b) => {
                let iv = self.eval(ie, env)?;
                match (b, iv) {
                    (Value::List(mut l), Value::Num(n)) => {
                        let i = n as usize;
                        let inner = l.get(i).cloned().unwrap_or(Value::Nothing);
                        let nv = self.assign_path(inner, &path[1..], v, env)?;
                        while l.len() <= i { l.push(Value::Nothing); }
                        l[i] = nv;
                        Ok(Value::List(l))
                    }
                    (Value::Obj(mut o), Value::Str(k)) => {
                        let inner = o.get(&k).cloned().unwrap_or(Value::Nothing);
                        let nv = self.assign_path(inner, &path[1..], v, env)?;
                        o.insert(k, nv);
                        Ok(Value::Obj(o))
                    }
                    (Value::Nothing, Value::Str(k)) => {
                        let mut o = BTreeMap::new();
                        o.insert(k, self.assign_path(Value::Nothing, &path[1..], v, env)?);
                        Ok(Value::Obj(o))
                    }
                    (b, i) => Err(Halt::Err(format!("인덱스 대입이 성립하지 않는다: {}[{}]", b.show(), i.show()))),
                }
            }
            (PathSeg::Member(k), Value::Nothing) => {
                let mut o = BTreeMap::new();
                o.insert(k.clone(), self.assign_path(Value::Nothing, &path[1..], v, env)?);
                Ok(Value::Obj(o))
            }
            (seg, b) => Err(Halt::Err(format!("대입 경로가 성립하지 않는다: {:?} on {}", seg, b.show()))),
        }
    }

    fn eval(&mut self, e: &Expr, env: &Rc<Env>) -> Exec<Value> {
        self.tick()?;
        match e {
            Expr::Num(n) => Ok(Value::Num(*n)),
            Expr::Str(s) => Ok(Value::Str(s.clone())),
            Expr::Ident(n) => {
                if n == "true" { return Ok(Value::Bool(true)); }
                if n == "false" { return Ok(Value::Bool(false)); }
                if n == "none" { return Ok(Value::Nothing); }
                if n == "ok" { return Ok(Value::Bool(true)); }
                env.get(n).ok_or_else(|| Halt::Err(format!("이름을 찾을 수 없다: {}", n)))
            }
            Expr::List(xs) => {
                let mut out = Vec::new();
                for x in xs { out.push(self.eval(x, env)?); }
                Ok(Value::List(out))
            }
            Expr::Obj(kvs) => {
                let mut o = BTreeMap::new();
                for (k, v) in kvs { let vv = self.eval(v, env)?; o.insert(k.clone(), vv); }
                Ok(Value::Obj(o))
            }
            Expr::Un(op, x) => {
                let v = self.eval(x, env)?;
                match (op.as_str(), v) {
                    ("-", Value::Num(n)) => Ok(Value::Num(-n)),
                    ("!", v) => Ok(Value::Bool(!v.truthy())),
                    (o, v) => Err(Halt::Err(format!("단항 {} 가 {} 에 성립하지 않는다", o, v.show()))),
                }
            }
            Expr::Bin(a, op, b) => {
                let (x, y) = (self.eval(a, env)?, self.eval(b, env)?);
                bin(op, x, y)
            }
            Expr::Member(x, name) => {
                // 효과 네임스페이스 차단 (H1) — never 목록에 오른 능력
                if let Expr::Ident(ns) = &**x {
                    if EFFECT_NS.contains(&ns.as_str()) && self.blocked.iter().any(|b| b == ns) {
                        return Err(Halt::Err(format!("never 가 막았다 — `{}` 능력은 이 task 에서 금지다 (H1: 계약은 선언이 아니라 차단이다)", ns)));
                    }
                }
                let v = self.eval(x, env)?;
                match v {
                    Value::Obj(o) => Ok(o.get(name).cloned().unwrap_or(Value::Nothing)),
                    Value::List(l) => {
                        if let Ok(i) = name.parse::<usize>() { Ok(l.get(i).cloned().unwrap_or(Value::Nothing)) }
                        else if name == "length" || name == "len" { Ok(Value::Num(l.len() as f64)) }
                        else { Ok(Value::Nothing) }
                    }
                    Value::Str(s) => {
                        if name == "length" || name == "len" { Ok(Value::Num(s.chars().count() as f64)) }
                        else { Ok(Value::Nothing) }
                    }
                    _ => Ok(Value::Nothing),
                }
            }
            Expr::Index(x, i) => {
                let (v, iv) = (self.eval(x, env)?, self.eval(i, env)?);
                match (v, iv) {
                    (Value::List(l), Value::Num(n)) => {
                        let idx = n as usize;
                        Ok(l.get(idx).cloned().unwrap_or(Value::Nothing))
                    }
                    (Value::Obj(o), Value::Str(k)) => Ok(o.get(&k).cloned().unwrap_or(Value::Nothing)),
                    (Value::Str(s), Value::Num(n)) => Ok(s.chars().nth(n as usize).map(|c| Value::Str(c.to_string())).unwrap_or(Value::Nothing)),
                    (v, i) => Err(Halt::Err(format!("인덱스가 성립하지 않는다: {}[{}]", v.show(), i.show()))),
                }
            }
            Expr::Lambda(p, b) => Ok(Value::Lambda(p.clone(), Rc::new((**b).clone()), env.clone())),
            Expr::IfExpr(c, a, b) => {
                if self.eval(c, env)?.truthy() { self.eval(a, env) } else { self.eval(b, env) }
            }
            Expr::Call(f, args) => {
                // 효과 호출 차단 (H1)
                if let Expr::Member(base, _) = &**f {
                    if let Expr::Ident(ns) = &**base {
                        if EFFECT_NS.contains(&ns.as_str()) && self.blocked.iter().any(|b| b == ns) {
                            return Err(Halt::Err(format!("never 가 막았다 — `{}` 능력은 이 task 에서 금지다 (H1)", ns)));
                        }
                    }
                }
                let mut vals = Vec::new();
                for a in args { vals.push(self.eval(a, env)?); }
                if let Expr::Ident(name) = &**f {
                    if let Some(v) = self.builtin(name, &vals, env)? { return Ok(v); }
                    if let Some(Value::Fn(fd)) = env.get(name) { return self.call_fn(&fd, vals, env); }
                    if let Some(Value::Lambda(p, b, ce)) = env.get(name) { return self.call_lambda(&p, &b, &ce, vals); }
                    return Err(Halt::Err(format!("호출할 수 없다: {}", name)));
                }
                let callee = self.eval(f, env)?;
                match callee {
                    Value::Fn(fd) => self.call_fn(&fd, vals, env),
                    Value::Lambda(p, b, ce) => self.call_lambda(&p, &b, &ce, vals),
                    other => Err(Halt::Err(format!("호출할 수 없다: {}", other.show()))),
                }
            }
        }
    }

    fn call_fn(&mut self, f: &Rc<FnDecl>, args: Vec<Value>, _env: &Rc<Env>) -> Exec<Value> {
        let base = Env::new();
        self.bind_globals(&base);
        let fenv = Env::child(&base);
        for (p, a) in f.params.iter().zip(args) { fenv.define(p, a); }
        match self.exec_block(&f.body, &fenv) {
            Ok(()) => Ok(Value::Nothing),
            Err(Halt::Return(v)) => Ok(v),
            Err(Halt::Fail(v)) => Ok(v),
            Err(e) => Err(e),
        }
    }

    fn call_lambda(&mut self, p: &str, b: &Rc<Expr>, closure: &Rc<Env>, args: Vec<Value>) -> Exec<Value> {
        let lenv = Env::child(closure);
        lenv.define(p, args.into_iter().next().unwrap_or(Value::Nothing));
        self.eval(b, &lenv)
    }

    /// 조합자와 내장 — 카드 v9A 에 명세된 것들
    fn builtin(&mut self, name: &str, a: &[Value], env: &Rc<Env>) -> Exec<Option<Value>> {
        let v = match (name, a) {
            // ── 컬렉션 조합자 ──
            ("map", [Value::List(l), f]) => {
                let mut out = Vec::new();
                for x in l { out.push(self.apply(f, vec![x.clone()], env)?); }
                Value::List(out)
            }
            ("filter", [Value::List(l), f]) => {
                let mut out = Vec::new();
                for x in l { if self.apply(f, vec![x.clone()], env)?.truthy() { out.push(x.clone()); } }
                Value::List(out)
            }
            ("sort", [Value::List(l)]) => {
                let mut c = l.clone();
                c.sort_by(cmp_value);
                Value::List(c)
            }
            ("sort", [Value::List(l), f]) => {
                let mut keyed = Vec::new();
                for x in l { keyed.push((self.apply(f, vec![x.clone()], env)?, x.clone())); }
                keyed.sort_by(|a, b| cmp_value(&a.0, &b.0));
                Value::List(keyed.into_iter().map(|(_, x)| x).collect())
            }
            ("group", [Value::List(l), f]) => {
                let mut o: BTreeMap<String, Value> = BTreeMap::new();
                for x in l {
                    let k = key_of(&self.apply(f, vec![x.clone()], env)?);
                    match o.entry(k).or_insert(Value::List(vec![])) {
                        Value::List(v) => v.push(x.clone()),
                        _ => {}
                    }
                }
                Value::Obj(o)
            }
            ("count", [Value::List(l)]) => {
                let mut o: BTreeMap<String, Value> = BTreeMap::new();
                for x in l {
                    let k = key_of(x);
                    let n = match o.get(&k) { Some(Value::Num(n)) => *n, _ => 0.0 };
                    o.insert(k, Value::Num(n + 1.0));
                }
                Value::Obj(o)
            }
            ("reduce", [Value::List(l), init, f]) => {
                let mut acc = init.clone();
                for x in l { acc = self.apply(f, vec![acc, x.clone()], env)?; }
                acc
            }
            ("take", [Value::List(l), Value::Num(n)]) => {
                Value::List(l.iter().take(*n as usize).cloned().collect())
            }
            // ── 저수준 내장 (카드 v9A 명세) ──
            ("split", [Value::Str(s), Value::Str(sep)]) => {
                let parts: Vec<Value> = if sep.is_empty() {
                    s.chars().map(|c| Value::Str(c.to_string())).collect()
                } else {
                    s.split(sep.as_str()).map(|p| Value::Str(p.to_string())).collect()
                };
                Value::List(parts)
            }
            ("split", [Value::Str(s)]) => {
                Value::List(s.split_whitespace().map(|p| Value::Str(p.to_string())).collect())
            }
            ("join", [Value::List(l), Value::Str(sep)]) => {
                Value::Str(l.iter().map(|v| plain(v)).collect::<Vec<_>>().join(sep))
            }
            ("trim", [Value::Str(s)]) => Value::Str(s.trim().to_string()),
            ("lower", [Value::Str(s)]) => Value::Str(s.to_lowercase()),
            ("upper", [Value::Str(s)]) => Value::Str(s.to_uppercase()),
            ("number", [v]) => Value::Num(plain(v).trim().parse::<f64>().unwrap_or(0.0)),
            ("text", [v]) => Value::Str(plain(v)),
            ("len", [v]) => match v {
                Value::List(l) => Value::Num(l.len() as f64),
                Value::Str(s) => Value::Num(s.chars().count() as f64),
                Value::Obj(o) => Value::Num(o.len() as f64),
                _ => Value::Num(0.0),
            },
            ("keys", [Value::Obj(o)]) => Value::List(o.keys().map(|k| Value::Str(k.clone())).collect()),
            ("values", [Value::Obj(o)]) => Value::List(o.values().cloned().collect()),
            ("push", [Value::List(l), x]) => {
                let mut c = l.clone(); c.push(x.clone()); Value::List(c)
            }
            ("has", [Value::Obj(o), Value::Str(k)]) => Value::Bool(o.contains_key(k)),
            ("has", [Value::List(l), x]) => Value::Bool(l.contains(x)),
            ("sum", [Value::List(l)]) => Value::Num(l.iter().map(num_of).sum()),
            ("min", [Value::List(l)]) => l.iter().cloned().min_by(cmp_value).unwrap_or(Value::Nothing),
            ("max", [Value::List(l)]) => l.iter().cloned().max_by(cmp_value).unwrap_or(Value::Nothing),
            ("first", [Value::List(l)]) => l.first().cloned().unwrap_or(Value::Nothing),
            ("last", [Value::List(l)]) => l.last().cloned().unwrap_or(Value::Nothing),
            ("range", [Value::Num(n)]) => Value::List((0..(*n as i64)).map(|i| Value::Num(i as f64)).collect()),
            ("range", [Value::Num(a0), Value::Num(b0)]) => Value::List(((*a0 as i64)..(*b0 as i64)).map(|i| Value::Num(i as f64)).collect()),
            _ => return Ok(None),
        };
        Ok(Some(v))
    }

    fn apply(&mut self, f: &Value, args: Vec<Value>, env: &Rc<Env>) -> Exec<Value> {
        match f {
            Value::Fn(fd) => self.call_fn(fd, args, env),
            Value::Lambda(p, b, ce) => {
                let lenv = Env::child(ce);
                let mut it = args.into_iter();
                lenv.define(p, it.next().unwrap_or(Value::Nothing));
                self.eval(&b.clone(), &lenv)
            }
            Value::Str(name) => {
                // 이름으로 넘긴 fn — `map(xs, double)` 에서 double 이 미정의 식별자로 왔을 때
                if let Some(Value::Fn(fd)) = env.get(name) { return self.call_fn(&fd, args, env); }
                Err(Halt::Err(format!("함수가 아니다: {}", name)))
            }
            other => Err(Halt::Err(format!("함수 자리에 {} 가 왔다", other.show()))),
        }
    }
}

fn plain(v: &Value) -> String {
    match v {
        Value::Str(s) => s.clone(),
        Value::Num(n) => if n.fract() == 0.0 { format!("{}", *n as i64) } else { format!("{}", n) },
        Value::Bool(b) => b.to_string(),
        other => other.show(),
    }
}
fn num_of(v: &Value) -> f64 {
    match v { Value::Num(n) => *n, Value::Str(s) => s.trim().parse().unwrap_or(0.0), Value::Bool(b) => if *b {1.0} else {0.0}, _ => 0.0 }
}
fn key_of(v: &Value) -> String { plain(v) }

fn cmp_value(a: &Value, b: &Value) -> std::cmp::Ordering {
    use std::cmp::Ordering;
    match (a, b) {
        (Value::Num(x), Value::Num(y)) => x.partial_cmp(y).unwrap_or(Ordering::Equal),
        (Value::Str(x), Value::Str(y)) => x.cmp(y),
        _ => num_of(a).partial_cmp(&num_of(b)).unwrap_or(Ordering::Equal),
    }
}

fn bin(op: &str, x: Value, y: Value) -> Exec<Value> {
    use Value::*;
    let v = match (op, &x, &y) {
        ("+", Str(a), b) => Str(format!("{}{}", a, plain(b))),
        ("+", a, Str(b)) => Str(format!("{}{}", plain(a), b)),
        ("+", _, _) => Num(num_of(&x) + num_of(&y)),
        ("-", _, _) => Num(num_of(&x) - num_of(&y)),
        ("*", _, _) => Num(num_of(&x) * num_of(&y)),
        ("/", _, _) => {
            let d = num_of(&y);
            if d == 0.0 { return Err(Halt::Err("0 으로 나눌 수 없다".into())); }
            Num(num_of(&x) / d)
        }
        ("%", _, _) => {
            let d = num_of(&y);
            if d == 0.0 { return Err(Halt::Err("0 으로 나머지를 구할 수 없다".into())); }
            Num(num_of(&x) % d)
        }
        ("==", _, _) => Bool(x == y),
        ("!=", _, _) => Bool(x != y),
        (">", _, _) => Bool(cmp_value(&x, &y) == std::cmp::Ordering::Greater),
        ("<", _, _) => Bool(cmp_value(&x, &y) == std::cmp::Ordering::Less),
        (">=", _, _) => Bool(cmp_value(&x, &y) != std::cmp::Ordering::Less),
        ("<=", _, _) => Bool(cmp_value(&x, &y) != std::cmp::Ordering::Greater),
        ("&&", _, _) => Bool(x.truthy() && y.truthy()),
        ("||", _, _) => Bool(x.truthy() || y.truthy()),
        (o, _, _) => return Err(Halt::Err(format!("연산자 {} 를 모른다", o))),
    };
    Ok(v)
}

/// `limit 200 ops` 류 자유 텍스트에서 ops 예산만 뽑는다
fn parse_ops_budget(limit: Option<&str>) -> Option<u64> {
    let s = limit?;
    let toks: Vec<&str> = s.split_whitespace().collect();
    for (i, t) in toks.iter().enumerate() {
        if t.starts_with("ops") || t.starts_with("op") {
            if i > 0 {
                if let Ok(n) = toks[i - 1].trim_end_matches(',').parse::<u64>() { return Some(n); }
            }
        }
    }
    None
}
