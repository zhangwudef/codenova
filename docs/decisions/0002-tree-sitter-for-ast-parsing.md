# ADR-0002: 选择 Tree-sitter 作为 AST 解析器

- **状态**: Accepted
- **日期**: 2026-08-01
- **决策者**: zhangwudef

## 背景

CodeNova 的核心能力之一是「AST 级语义切分」——将源代码按函数/类/方法粒度切分，避免固定长度切分破坏代码结构。这需要一个能解析多种编程语言的 AST 解析器。

## 考虑的方案

| 方案 | 多语言支持 | 增量解析 | 性能 | 生态 |
|------|-----------|---------|------|------|
| Tree-sitter | ✅ 30+ 语言 | ✅ | ✅ C 实现，极快 | ✅ GitHub/Neovim 背书 |
| 各语言原生 parser（ast/typed-ast） | ❌ 每种语言独立 | ❌ | 🟡 Python 解释器内 | ❌ 碎片化 |
| Babylon / SWC | ❌ 偏 JS/TS | ❌ | ✅ | ❌ JS 生态 |
| ctags | ✅ 符号提取 | ❌ | ✅ | ❌ 仅符号，非完整 AST |

## 决策

选择 **Tree-sitter**，使用各语言的独立 Python 绑定包（`tree-sitter-python`、`tree-sitter-javascript` 等）。

## 理由

1. **统一 API**：一套 API 解析 6 种语言（Python/JS/TS/Java/Go/Rust），无需为每种语言引入不同的解析库
2. **C 实现，性能高**：解析速度远快于 Python 原生 ast 模块
3. **容错性强**：即使代码有语法错误，Tree-sitter 仍能产出部分 AST（其他解析器会直接报错退出）
4. **生态成熟**：GitHub Codesearch、Neovim、Atom 均使用 Tree-sitter，长期维护有保障
5. **预编译 wheel**：各语言绑定包提供 manylinux/macos/win 轮子，安装无需编译

## 后果

**正面**：
- 多语言支持成本低，新增语言只需加一个 `tree-sitter-xxx` 包
- 解析速度快，实测 37 文件解析 < 0.1s
- 容错性确保即使有语法错误的文件也能切分

**负面**：
- 增加了 7 个 `tree-sitter-*` 依赖，安装体积较大（但都是预编译 wheel）
- Tree-sitter 的 query 语法有学习曲线
- 不同语言包版本更新节奏不一，偶有 ABI 不兼容（已通过锁定版本规避）

## 参考

- [Tree-sitter 官网](https://tree-sitter.github.io/)
- S1 基准测试结果：[docs/benchmark.md §11](../benchmark.md#11-s1-真实运行结果)
