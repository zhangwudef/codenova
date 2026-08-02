# ADR-0001: 记录架构决策（使用 ADR）

- **状态**: Accepted
- **日期**: 2026-08-01
- **决策者**: zhangwudef

## 背景

CodeNova 在技术选型与架构设计上有多个关键决策点（AST 解析器选型、向量数据库选型、切分策略、双索引设计等）。这些决策的"为什么"如果只存在于代码或脑海中，随时间推移会难以追溯，导致：

- 新贡献者不理解为何选择某技术，可能提出已被否决的方案
- 重构时无意违反原始约束
- 技术债务积累时缺乏判断基准

## 决策

采用 **ADR（Architecture Decision Records）** 模式，在 `docs/decisions/` 目录下以编号 Markdown 文件记录每个重要架构决策。

### ADR 格式

每个 ADR 文件遵循以下结构：
- **标题**: `ADR-XXXX: 简短描述`
- **状态**: Proposed / Accepted / Deprecated / Superseded by ADR-YYYY
- **背景**: 为什么需要做这个决策
- **决策**: 选择了什么
- **理由**: 为什么选这个，考虑过哪些替代方案
- **后果**: 这个决策带来的影响（正面与负面）

### 编号规则

- 从 0001 开始递增，不回收编号
- 被 superseded 的 ADR 保留原内容，在头部标注 `Superseded by ADR-YYYY`

## 后果

**正面**：
- 决策可追溯，新成员可快速理解技术选型背景
- 避免重复讨论已决策的问题
- 技术演进的脉络清晰可见

**负面**：
- 需要维护 ADR 文档的纪律
- 决策变更时需新建 ADR 而非直接修改旧的

## 参考

- [Michael Nygard - Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [ADR GitHub Organization](https://adr.github.io/)
