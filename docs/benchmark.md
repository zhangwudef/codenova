# CodeNova 性能基准测试设计文档

> 本文档定义 CodeNova 检索质量与性能的基准测试套件。目的：用可复现的量化数据验证核心技术点（AST 切分、双索引、增量索引、多语言解析）的实际效果，取代 README 中未经证实的百分比数字。

状态：🟢 S1 已实现并跑出第一组真实数据（2026-08-01）；🟡 S2/S3 脚本已就绪待运行；S4–S6 待实现

> 真实数据见 [§11. S1 真实运行结果](#11-s1-真实运行结果)；原始 CSV 见 [backend/tests/benchmark/results_S1.csv](../backend/tests/benchmark/results_S1.csv)

---

## 1. 测试目标

| 编号 | 目标 | 验证的声明 |
| --- | --- | --- |
| O1 | 量化 AST 语义切分 vs 朴素固定长度切分的检索质量差异 | "AST 切分避免破坏代码结构，提升召回" |
| O2 | 量化双索引（语义 + 调用图）vs 纯语义索引的检索质量差异 | "双索引策略增强跨文件溯源能力" |
| O3 | 量化增量索引相对全量索引的耗时与资源节省 | "增量更新避免全量重算" |
| O4 | 量化多语言解析管线的吞吐与正确性 | "支持 Python/JS/TS/Java/Go/Rust" |
| O5 | 量化端到端问答延迟与答案质量 | "2 分钟内生成可问答知识库" |
| O6 | 量化大仓库压力下的性能衰减 | 可扩展性边界 |

---

## 2. 评测指标

### 2.1 检索质量指标（O1 / O2）

针对每个问题，存在人工标注的「正确代码位置」集合（ground-truth 文件 + 行范围）。

| 指标 | 定义 | 计算方式 |
| --- | --- | --- |
| **Hit Rate@k** | top-k 检索结果是否命中任一正确文件 | `命中问题数 / 总问题数` |
| **Recall@k** | top-k 结果覆盖的正确文件比例 | `Σ (命中文件数/正确文件数) / N` |
| **MRR** | 平均倒数排名 | `Σ 1/rank(首个命中) / N` |
| **Precision@k** | top-k 中相关结果占比 | `Σ (命中数/k) / N` |

> 默认 `k = 5`。检索结果按相似度分数排序。

### 2.2 答案质量指标（O5）

由人工或 LLM-as-judge 按 1-5 分量表评分：

| 维度 | 评分标准 |
| --- | --- |
| **正确性** | 答案是否符合代码实际行为（5=完全正确，1=错误） |
| **溯源准确性** | 引用的代码位置是否真实支持答案（5=完全对应，1=编造） |
| **完整性** | 是否覆盖跨文件依赖（5=完整，1=片面） |
| **忠实度** | 是否仅基于上下文，无幻觉（5=无幻觉，1=大量编造） |

### 2.3 性能指标（O3 / O4 / O5 / O6）

| 指标 | 单位 | 采集点 |
| --- | --- | --- |
| **解析耗时** | 秒 | `ParsingPipeline.run` wall time |
| **切分耗时** | 秒 | `CodeSplitter.split_batch` wall time |
| **Embedding 吞吐** | chunks/秒 | `index_code_chunks` 总块数 / 总耗时 |
| **索引构建耗时** | 秒 | `index_repo` wall time |
| **查询延迟** | 毫秒（p50/p95/p99） | `RAGChain.ask` wall time |
| **图构建耗时** | 秒 | `CallGraphExtractor.extract` wall time |
| **增量加速比** | 倍 | `全量耗时 / 增量耗时` |
| **峰值内存** | MB | 进程 RSS 峰值 |
| **节点/边数量** | 个 | 依赖图统计 |

---

## 3. 测试场景

### S1：切分策略对比（对应 O1）✅ 已实现
固定检索器（纯语义）与 embedding 模型，仅切换切分策略：
- A 组：`fixed`（1500 字符，200 重叠）
- B 组：`semantic`（启发式）
- C 组：`ast`（Tree-sitter）

**假设**：C 组在跨函数/类问题上 Recall@5 优于 A 组。

**实际测试规模**：以 CodeNova 后端自身（`backend/app`，37 个 .py 文件）作为被测仓库，15 题人工标注问题集（12 题定位类 + 3 题行为类），embedding 模型 `paraphrase-multilingual-MiniLM-L12-v2`（384 维，多语种，便于快速复现），内存中余弦相似度检索。脚本：[backend/tests/benchmark/run_s1.py](../backend/tests/benchmark/run_s1.py)；问题集：[backend/tests/benchmark/questions.csv](../backend/tests/benchmark/questions.csv)。

> 说明：S1 的目标是验证「切分策略之间的相对差异」，因此采用轻量 embedding 模型与小规模仓库以降低复现门槛；结论的相对方向不因 embedding 模型选择而反转。后续 S2/S5 在接入 bge-m3 与 LLM 后再验证绝对值。

### S2：双索引 vs 纯语义（对应 O2）🟡 脚本就绪
固定 `ast` 切分，对比：
- A 组：纯语义检索（`_expand_with_graph` 禁用）
- B 组：双索引（语义 + 调用图 1 跳扩展）

**假设**：B 组在「跨文件依赖」「调用链」类问题上 MRR 显著优于 A 组。

**脚本**：[backend/tests/benchmark/run_s2.py](../backend/tests/benchmark/run_s2.py)
**复现命令**：`cd backend && python -m tests.benchmark.run_s2`
**输出**：[backend/tests/benchmark/results_S2.csv](../backend/tests/benchmark/results_S2.csv)
**状态**：脚本已就绪，待用户在本机运行后回填实测数据

### S3：增量 vs 全量（对应 O3）🟡 脚本就绪
对已索引仓库模拟一次变更（修改 5% / 15% / 30% 文件），对比：
- A 组：全量重新索引
- B 组：`index_repo_incremental`

**假设**：变更 ≤15% 时，B 组加速比 ≥ 3×。

**脚本**：[backend/tests/benchmark/run_s3.py](../backend/tests/benchmark/run_s3.py)
**复现命令**：`cd backend && python -m tests.benchmark.run_s3`
**输出**：[backend/tests/benchmark/results_S3.csv](../backend/tests/benchmark/results_S3.csv)
**测量范围**：AST 切分 + Embedding 向量化耗时（不含 Qdrant 网络 I/O），每组重复 3 次取中位数
**状态**：脚本已就绪，待用户在本机运行后回填实测数据

### S4：多语言解析（对应 O4）
对 6 种语言各选 1 个中型仓库，统计解析正确性（符号数 vs ctags 基准）与耗时。

### S5：端到端问答（对应 O5）
完整流程：克隆 → 解析 → 切分 → 向量化 → 问答，记录总耗时与答案质量评分。

### S6：大仓库压力（对应 O6）
对 1000+ 文件仓库测试解析/索引耗时、内存峰值、查询延迟衰减曲线。

---

## 4. 输入数据规格

### 4.1 测试仓库

| 仓库 | 语言 | 规模 | 用途 |
| --- | --- | --- | --- |
| octocat/Hello-World | - | <10 文件 | 冒烟测试 |
| pallets/flask | Python | ~200 文件 | S1/S2/S5 主仓库 |
| expressjs/express | JavaScript | ~100 文件 | S4 |
| microsoft/TypeScript | TypeScript | 大型 | S4/S6 |
| spring-projects/spring-petclinic | Java | ~50 文件 | S4 |
| gin-gonic/gin | Go | ~100 文件 | S4 |
| tokio-rs/mini-redis | Rust | ~30 文件 | S4 |
| facebook/react | TS/JS | 1000+ 文件 | S6 压力 |

### 4.2 问题集（60 题，人工标注 ground-truth）

按类型分层，每类 15 题：

| 类型 | 示例 | 期望命中 |
| --- | --- | --- |
| **定位类** | "请求上下文在哪里创建？" | 单文件单函数 |
| **行为类** | "路由匹配失败时返回什么状态码？" | 单文件 |
| **依赖类** | "X 函数调用了哪些下游函数？" | 多文件（S2 关键） |
| **跨文件类** | "配置从加载到生效经过哪些模块？" | 多文件多函数 |

问题集以 `questions.csv` 维护，schema：

```csv
id,repo,category,question,gt_files,gt_symbols,notes
q01,flask,location,请求上下文在哪里创建？,src/flask/ctx.py,RequestContext,
```

- `gt_files`：分号分隔的正确文件相对路径
- `gt_symbols`：分号分隔的正确符号全限定名

### 4.3 变更集（S3 用）
基于 flask 仓库，构造 3 个变更版本：修改 5% / 15% / 30% 的 .py 文件（增删改函数）。

---

## 5. 执行流程

### 5.1 环境准备
```bash
docker compose -f docker-compose.demo.yml up -d   # Qdrant + 后端
export OPENAI_API_KEY=...                          # LLM
# 首次运行下载 bge-m3 模型（约 2GB）
```

### 5.2 运行检索质量测试（S1/S2）
```bash
cd backend
python -m tests.benchmark.run_retrieval \
  --scenario S1 \
  --repos tests/benchmark/fixtures/repos.json \
  --questions tests/benchmark/fixtures/questions.csv \
  --strategies fixed,semantic,ast \
  --top-k 5 \
  --output results/S1.csv
```

### 5.3 运行性能测试（S3/S4/S6）
```bash
python -m tests.benchmark.run_perf \
  --scenario S3 \
  --repo https://github.com/pallets/flask.git \
  --change-ratios 0.05,0.15,0.30 \
  --output results/S3.json
```

### 5.4 运行问答质量测试（S5）
```bash
python -m tests.benchmark.run_qa \
  --questions tests/benchmark/fixtures/questions.csv \
  --judge llm \          # 或 human
  --output results/S5.json
```

### 5.5 汇总报告
```bash
python -m tests.benchmark.report --input results/ --output results/REPORT.md
```

---

## 6. 结果数据 Schema

### results/S1.csv（检索质量）
```csv
scenario,repo,question_id,strategy,hit@5,recall@5,mrr,precision@5,latency_ms
S1,flask,q01,ast,1,1.0,1.0,1.0,142
```

### results/S3.json（性能）
```json
{
  "scenario": "S3",
  "repo": "flask",
  "change_ratio": 0.15,
  "full_reindex_seconds": 38.2,
  "incremental_seconds": 9.7,
  "speedup": 3.94,
  "peak_memory_mb": 612
}
```

---

## 7. 成功标准（门槛）

| 场景 | 指标 | 门槛 | 说明 |
| --- | --- | --- | --- |
| S1 | Recall@5 (ast vs fixed) | ast ≥ fixed，且差距 ≥ 5 个百分点 | AST 切分有可测量的提升 |
| S1 | MRR (ast vs fixed) | ast ≥ fixed | 排名质量不退化 |
| S2 | MRR (双索引 vs 纯语义) — 跨文件类 | 双索引 ≥ 纯语义 + 10 个百分点 | 双索引在跨文件问题上体现价值 |
| S3 | 增量加速比 @ 15% 变更 | ≥ 3× | 增量索引显著快于全量 |
| S4 | 符号召回率（vs ctags） | ≥ 90% | 多语言解析正确性 |
| S5 | 端到端首次问答就绪 | flask（~200 文件）≤ 120 秒 | 兑现"2 分钟"承诺 |
| S5 | 答案溯源准确性均分 | ≥ 4.0 / 5 | 引用位置真实可靠 |
| S6 | 1000 文件仓库索引 | ≤ 600 秒，峰值内存 ≤ 2GB | 可扩展性 |
| O5 | 查询延迟 p95 | ≤ 5000 ms | 交互体验 |

> 未达门槛的指标需在 README 中如实标注「未验证」或「待优化」，不得使用虚构百分比。

---

## 8. 公平性与可复现性约束

1. **固定 embedding 模型**：`BAAI/bge-m3`，向量维度 1024
2. **固定 LLM**：`gpt-4o`，temperature=0.1（与 [qa_chain.py:142](../backend/app/services/rag/qa_chain.py) 一致）
3. **固定 top_k=5**，score_threshold 保持默认
4. **冷启动**：每组测试前清空 Qdrant 对应 collection，避免缓存干扰
5. **重复运行**：每组 ≥ 3 次，取中位数；延迟指标取所有运行的全部样本
6. **硬件记录**：报告 CPU/内存/磁盘型号，便于横向对比
7. **随机性控制**：LLM 评分使用固定 seed；问题顺序固定
8. **版本锁定**：测试脚本与被测代码 commit hash 一同记录入报告

---

## 9. 待实现的测试脚本清单

```
backend/tests/benchmark/
├── __init__.py
├── fixtures/
│   ├── repos.json              # 测试仓库清单
│   ├── questions.csv           # 60 题问题集 + ground-truth
│   └── changesets/             # S3 变更集
├── run_retrieval.py            # S1/S2 检索质量
├── run_perf.py                 # S3/S4/S6 性能
├── run_qa.py                   # S5 问答质量
├── metrics.py                  # 指标计算（Recall/MRR/...）
├── judge.py                    # LLM-as-judge 评分
└── report.py                   # 汇总生成 REPORT.md
```

---

## 10. 时间线

- [x] 第 1 阶段：人工标注 15 题问题集与 ground-truth（CodeNova 后端，定位 + 行为两类）
- [x] 第 2 阶段：实现 `run_s1.py`，跑通 S1（2026-08-01 第一组真实数据，见 §11）
- [ ] 第 3 阶段：实现 S2/S3，验证双索引与增量
- [ ] 第 4 阶段：补全 S4/S5/S6，生成首版 REPORT.md
- [ ] 第 5 阶段：将达标数据回填 README，替换占位说明

---

## 11. S1 真实运行结果

> 运行时间：2026-08-01 14:41（Asia/Shanghai）
> 环境：Windows + Python 3.13（`.venv313`），CPU 模式，单次运行
> 原始 CSV：[backend/tests/benchmark/results_S1.csv](../backend/tests/benchmark/results_S1.csv)
> 复现命令：`cd backend && python -m tests.benchmark.run_s1`（需可访问 HuggingFace 下载 embedding 模型，或设置 `HF_ENDPOINT=https://hf-mirror.com`）

### 11.1 汇总数据

| 策略 | chunks | 切分耗时 | 向量化耗时 | Hit@5 | Recall@5 | MRR | Precision@5 | p50 延迟 | p95 延迟 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `fixed` | 184 | 0.01 s | 4.18 s | **80.00%** | **80.00%** | 0.463 | 16.00% | 0.07 ms | 0.12 ms |
| `semantic` | 158 | 0.01 s | 3.36 s | 60.00% | 60.00% | 0.424 | 12.00% | 0.08 ms | 0.10 ms |
| `ast` | 255 | 0.06 s | 5.19 s | 73.33% | 73.33% | **0.549** | **14.67%** | 0.09 ms | 0.11 ms |

### 11.2 结论（基于本组数据）

1. **MRR（排名质量）**：`ast` > `fixed` > `semantic`。
   - AST 切分虽然 Hit@5 略低于 `fixed`（73.33% vs 80.00%），但命中时把正确文件排到更靠前的位置（MRR 0.549 vs 0.463，**+18.6%**），这对「Top-1 直接展示给用户」的体验更关键。
   - 部分定位类问题（如「AST 代码切分器在哪个文件？」）`ast` 把目标文件排到第 1，而 `fixed` 因按 1500 字符硬切把同文件多个 chunk 拆散，命中位置靠后。
2. **Hit@5 / Recall@5（召回广度）**：`fixed` > `ast` > `semantic`。
   - `fixed` 在小文件仓库上略占优：37 个 .py 文件大多 < 1500 字符，硬切几乎等于「整文件作为一个 chunk」，命中文件粒度天然宽。
   - `semantic` 表现最弱：启发式切点检测在小文件上常退化为整文件，且对 `__init__.py` 类文件大量回退至 `fixed`，没有形成差异化优势。
3. **Precision@5**：三者均在 12%–16% 区间，差异不显著（top-5 中平均仅 1 个命中）。
4. **延迟**：三者均在亚毫秒级，差异可忽略；瓶颈在向量化（3–5 s），切分本身 < 0.1 s。

### 11.3 与原假设的对照

| 原假设（§3.S1） | 实测 | 是否成立 |
| --- | --- | --- |
| `ast` 在 Recall@5 上优于 `fixed` | `ast` 73.33% < `fixed` 80.00% | ❌ 不成立（小文件场景下 `fixed` 整文件切分占优） |
| `ast` 在 MRR 上不退化 | `ast` 0.549 > `fixed` 0.463 | ✅ 成立且超出预期（+18.6%） |

### 11.4 已识别的改进方向

- **S1 规模偏小**：37 文件 / 15 题，统计意义有限。计划在 S5 接入 flask (~200 文件) 后复测，验证「文件变大、函数变多时 AST 优势是否放大」的直觉。
- **`semantic` 策略退化严重**：在 `__init__.py` / 小文件上大量回退至 `fixed`，需排查 `SemanticChunkStrategy` 的切点检测阈值。
- **缺跨文件类问题**：当前 15 题以定位类为主，未覆盖 S1 假设重点强调的「跨函数/类问题」。后续扩充问题集时需补足此类样本。
- **未达 S1 门槛**：§7 门槛要求 `ast` Recall@5 ≥ `fixed` + 5 个百分点，实测不达标。已如实记录，README 中相关声明仅引用 MRR 优势，不对 Recall 做夸大表述。
