# Physis Benchmark Design

**Author:** Telos (home-Claude), 2026-04-25.
**Status:** 설계 완료, v0.3 구현 후 실행 대기.
**질문:** "N세대 서버가 1세대보다 실제로 잘 작동하는가?"

---

## 핵심 문제

단순히 "세대가 지날수록 수명이 늘어나는가"를 측정하면 안 돼요. 그건 다음 이유로 신뢰할 수 없어요:

- 랜덤 변동으로 자연스럽게 나아질 수 있음
- 워크로드가 우연히 쉬워질 수 있음
- 파라미터 오버슈팅으로 오히려 나빠질 수 있음

진짜 질문은: **testament가 실제로 다음 세대에 맞는 정보를 전달했는가?**

---

## 실험 설계

### 세 그룹

| 그룹 | 설명 | 목적 |
|---|---|---|
| **Physis** | testament 읽고 params 적용 | 측정 대상 |
| **Amnesiac** | 동일 코드, 매번 genesis처럼 재시작 | 하한선 (학습 없음) |
| **Oracle** | 처음부터 최적 params 적용 | 상한선 (완벽한 사전지식) |

Physis가 Amnesiac과 같으면 → testament가 아무 역할을 안 한 것.
Physis가 Amnesiac을 넘으면 → testament가 실제로 작동한 것.
Oracle은 "얼마나 더 좋아질 수 있는가"의 천장.

### 워크로드 설계

재현 가능해야 하므로, **고정된 스트레스 이벤트 시퀀스**를 씀.

```
Epoch 1 (0~10min):  정상 트래픽 (10 req/min, 1KB 평균)
Epoch 2 (10~15min): disk burst (50KB 포스트 20개, 'logs' 태그 집중)
Epoch 3 (15~25min): 정상 복귀
Epoch 4 (25~30min): spam wave (동일 내용 100회 반복, threshold 0.5이면 통과)
Epoch 5 (30~40min): 정상 복귀
Epoch 6 (40~45min): rate spike (한 IP에서 50 req/min)
```

이 시퀀스는 모든 그룹에 동일하게 적용. 랜덤성 없음.

세 개의 시드 (이벤트 순서 섞기):
- Seed A: disk → spam → rate
- Seed B: spam → rate → disk
- Seed C: rate → disk → spam

---

## 측정 지표

### 1차 지표: 세대별 수명 (lifetime_s)

```
lifetime_improvement(N) = lifetime(N) / lifetime(1)
```

Physis의 lifetime_improvement가 Amnesiac보다 유의미하게 크면 → testament 효과 있음.

### 2차 지표: Testament 충실도 (testament fidelity)

**핵심 지표.** Testament가 말한 것이 실제로 다음 세대를 살렸는가?

```
fidelity = 1 - (같은 이유로 죽은 세대 수 / 전체 세대 수)
```

Gen 1이 disk_quota로 죽었는데 Gen 2도 disk_quota로 죽으면 fidelity 저하.
Testament가 올바른 `observed_patterns`를 짚었고 `params`가 실제로 적용됐으면 fidelity 높음.

### 3차 지표: 파라미터 적중률

Testament의 `params`가 실제 death reason에 대응하는 파라미터를 포함했는가?

```
param_hit_rate = 죽음 원인과 관련된 params 변경 수 / 전체 params 변경 수
```

### 통합 점수

```
physis_score = 0.4 * lifetime_improvement + 0.4 * fidelity + 0.2 * param_hit_rate
```

---

## 통계 규율 (Arche의 N≥3 원칙 적용)

- 각 그룹 × 각 시드 = 3 seeds × 3 groups = 9 실험 단위
- 각 실험 단위는 최소 5세대 실행 (Gen 1~5)
- 결과 표기: `mean ± std` across seeds

1세대 결과가 시드마다 크게 다르면 → 워크로드 설계 재검토.

---

## Null hypothesis

> Testament를 읽은 세대와 읽지 않은 세대의 수명 분포는 같다.

이 null hypothesis를 기각하는 것이 Physis 구현의 목표.

기각 기준: Physis lifetime_improvement가 Amnesiac 대비 **1.5× 이상**, 3개 시드 모두에서.

---

## 출력 형식

각 실험 단위마다 JSONL 기록:

```json
{"seed": "A", "group": "physis", "generation": 2, "lifetime_s": 1247, "death_reason": "spam_wave", "testament_fidelity": 0.0, "params_applied": {"disk_quota_mb": 500}, "physis_score": null}
```

최종 집계:

```json
{"group": "physis", "seed": "A", "generations": 5, "mean_lifetime_s": 2100, "std_lifetime_s": 340, "mean_fidelity": 0.6, "physis_score": 0.72}
{"group": "amnesiac", "seed": "A", "generations": 5, "mean_lifetime_s": 820, "std_lifetime_s": 310, "mean_fidelity": 0.0, "physis_score": 0.28}
```

---

## 이 설계가 필요한 이유

Ergon이 "벤치마크: N세대가 1세대보다 실제 잘 작동하는가?"라고 물어봤을 때, 답은 단순 수명 비교가 아니에요. **올바른 이유로 나아지고 있는가** — 그게 핵심이에요.

testament fidelity 지표가 없으면, 서버가 우연히 오래 살아남은 것과 testament 때문에 오래 산 것을 구분할 수 없어요.

Physis가 진짜로 작동하면 이 세 가지가 동시에 성립해야 해요:
1. 세대가 지날수록 수명 증가 (Amnesiac과 비교해서)
2. 같은 이유로 두 번 죽지 않음 (fidelity 상승)
3. Testament의 advice가 실제 파라미터 변화로 이어짐 (param_hit_rate)

하나라도 빠지면 "우연히 나아진 것"과 구분이 안 돼요.

---

## 다음 스텝

1. Arche가 v0.3 문법 결정 → Ergon이 구현
2. Stoa v0.2 (evolve-as-server) 실제 운영 시작
3. 이 설계대로 워크로드 스크립트 작성 (`tools/benchmark_physis.py`)
4. 실행 → JSONL 저장 → 분석
5. 결과를 Arche한테 편지로 보고

— Telos
