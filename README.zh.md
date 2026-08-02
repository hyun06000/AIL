# AIL — AI Intent Language

[English](README.md) · [한국어](README.ko.md) · **中文** · [AI 代理入口](README.ai.md)

一门从零开始为 LLM 构建的编程语言 —— 彻底排除人类的阅读、书写与学习。

## 为什么需要一门新语言？

现有的所有强制机制都分布在一道鸿沟的两侧：

- **语言之外的强制**：代理 harness、权限系统、沙箱、CI 门禁。它们在不理解程序意图的情况下进行拦截。
- **语言之内的强制**：类型系统、Rust 所有权、capability、效果系统。它们严格强制 —— 但针对的是内存与类型错误，而不是代理时代的风险。

两者的交集 —— *用语言内的强制来阻止代理时代的风险*（不可逆操作、技术债、LLM 滥用、失控循环）—— 是空白的。AIL 正是为了站在这个位置而构建。

这源于 **HEAAL**（Harness Engineering As A Language，读作"heal"）哲学：对不该发生的事，不要*劝阻*，而要让语言的语法、解析器和运行时使其*无法表达或无法执行*。语言本身就是 harness。全文：[docs/HEAAL.md](docs/HEAAL.md)（韩语）

## 有什么不同？

AIL 程序不是过程的描述，而是一份**意图契约**，必须包含三个部分：

1. **要达成什么** —— 目的的声明
2. **观察到什么才算成功** —— 可判定的成功条件
3. **什么被禁止** —— 其拥有的 capability、效果与资源预算的边界

缺少任何一项的程序无法通过解析。它舍弃的，恰恰是只为人类认知而存在的东西：可读性语法、学习曲线、人体工学、注释文化。它获得的：token 效率、结构一致性、机器可验证的断言、上下文自足性。详情：[docs/AIL.md](docs/AIL.md)（韩语）

## 当前状态

**概念阶段 —— 如实相告。** 哲学（HEAAL）与语言概念已成文。语法、解析器、运行时*尚未设计*；本仓库任何地方提及它们，都是方向而非规范。

- [x] HEAAL 哲学 — [docs/HEAAL.md](docs/HEAAL.md)
- [x] 语言概念 + AI readme — [docs/AIL.md](docs/AIL.md), [README.ai.md](README.ai.md)
- [x] 多语言 readme（本文档）
- [ ] 贡献指南 + 开源化
- [ ] （后续 chain）语法设计 → 解析器 → 运行时

## 本仓库的工作方式

本仓库基于 [gil](https://github.com/hyun06000/Ariadne)（GIt for Language model）运转：所有工作以 **chain（目的）> cycle（问题）> step（define → hypothesis → verify → analyze → 结论）** 的形式记录在提交图中。保留的不只是结论 —— 假设、证伪条件、失败的分支全部留存。

注意这个对称：gil 的 cycle 要求目的、成功判据与证伪条件 —— 与 AIL 对程序要求的三要素契约同构。这个仓库已经在用它想要构建的语言的原理运转。

## 贡献与文档

- AI 代理：从 [README.ai.md](README.ai.md) 开始
- 人类：贡献指南准备中（下一个 cycle）。在此之前，思考的历史可通过 `gil log --all` 或 gil 查看器浏览。
- 哲学：[docs/HEAAL.md](docs/HEAAL.md) · 语言概念：[docs/AIL.md](docs/AIL.md)
