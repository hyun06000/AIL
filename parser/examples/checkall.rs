fn main() {
    for f in ["P4-ail-v9A","P7-ail-v9A","P10x-ail-v9A","P10y-ail-v9A","P10z-ail-v9A","P5y-ail-v9A","P5z-ail-v9A"] {
        let p = format!("../experiments/scale/{}.txt", f);
        match std::fs::read_to_string(&p).map(|s| ail_parser::parse_program(&s)) {
            Ok(Ok(_)) => println!("  {}: 파싱 OK", f),
            Ok(Err(e)) => println!("  {}: REJECT — {}", f, e),
            Err(_) => println!("  {}: 파일 없음", f),
        }
    }
}
