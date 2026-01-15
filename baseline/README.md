# Baseline Agent 方案

## 📋 概述

Baseline Agent 是一个基于 CSV 文件的智能查询方案，用于与 DbRheo NL2SQL Agent 进行对比测试。

**核心特点**：
- 直接读取 CSV 文件，无需数据库
- LLM 生成过滤条件 → Pandas 过滤 → LLM 分析
- 适合离线场景和快速原型验证

## 📁 目录结构

```
baseline/
├── README.md                      # 本文件
├── baseline_agent_enhanced.py     # ✅ 主要实现（推荐使用）
├── baseline_agent_rag.py          # RAG 版本（使用向量检索）
├── baseline_agent_rag_chroma.py   # ChromaDB 版本
├── baseline_agent.py              # 基础版本
├── create_clean_database.py       # 数据库清理工具
├── init_chroma.py                 # ChromaDB 初始化
├── 数据源_销量.csv                 # ✅ 主数据文件
├── 测试集_月同比.csv               # 测试集（预计算指标）
├── 课题数据(1).csv                 # 原始数据
├── chroma_db/                     # ChromaDB 向量数据库
└── data_scripts/                  # 数据处理脚本
    ├── split_csv.py               # CSV 拆分工具
    ├── import_to_sqlite.py        # SQLite 导入工具
    └── README.md                  # 数据脚本说明
```

## 🚀 快速开始

### 1. 环境配置

确保 `.env` 文件中配置了以下变量：

```bash
# Baseline Agent 配置
BASELINE_OPENAI_API_KEY=your_api_key
BASELINE_OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
BASELINE_MODEL=qwen-flash
BASELINE_CSV_PATH=数据源_销量.csv
```

### 2. 使用 Baseline Agent

**方式1：通过 Gradio Web 界面**（推荐）

```bash
# 在项目根目录运行
python gradio_app.py
```

然后在浏览器中访问 `http://localhost:7860`，选择 "📈 Baseline Agent" 标签页。

**方式2：直接调用**

```python
from baseline_agent_enhanced import EnhancedBaselineAgent

# 初始化
agent = EnhancedBaselineAgent("baseline/数据源_销量.csv")

# 查询
result = agent.query("2023年比亚迪的总销量是多少？")

print(result["answer"])
```

## 📊 Agent 版本对比

| 版本 | 文件 | 特点 | 推荐度 |
|------|------|------|--------|
| **Enhanced** | `baseline_agent_enhanced.py` | LLM生成过滤条件，Pandas过滤，结构化输出 | ⭐⭐⭐⭐⭐ |
| **RAG** | `baseline_agent_rag.py` | 使用向量检索，适合大文件 | ⭐⭐⭐ |
| **ChromaDB** | `baseline_agent_rag_chroma.py` | 使用ChromaDB向量数据库 | ⭐⭐⭐ |
| **Basic** | `baseline_agent.py` | 基础实现 | ⭐⭐ |

**推荐使用 `baseline_agent_enhanced.py`**，它提供了最好的性能和可靠性。

## 🔧 数据文件说明

### 主数据文件

- **数据源_销量.csv**：主要数据文件，包含车型销量数据
  - 时间范围：2005-01 ~ 2030-12
  - 数据类型：销量数据、市场份额数据
  - 格式：`indicator_id, display_name, unit, value, date`

### 测试文件

- **测试集_月同比.csv**：包含预计算的同比/环比指标，用于验证计算准确性
- **课题数据(1).csv**：原始完整数据文件

## 🛠️ 数据处理工具

### 拆分 CSV 文件

将原始数据拆分为测试集和数据源：

```bash
cd baseline/data_scripts
python split_csv.py
```

**输出**：
- `../测试集_月同比.csv` - 测试集（同比/环比指标）
- `../数据源_销量.csv` - 数据源（原始销量数据）

### 导入 SQLite 数据库

将数据导入 SQLite 数据库（供 DbRheo Agent 使用）：

```bash
cd baseline/data_scripts
python import_to_sqlite.py
```

**输出**：
- `../../db/vehicle_sales.db` - SQLite 数据库

详细说明请参考 `data_scripts/README.md`。

## 📈 性能对比

### Baseline Agent vs DbRheo Agent

| 特性 | Baseline Agent | DbRheo Agent |
|------|---------------|--------------|
| **数据源** | CSV 文件 | SQLite 数据库 |
| **查询方式** | Pandas 过滤 | SQL 查询 |
| **计算方式** | LLM 分析 | SQL 聚合 + Python 计算 |
| **准确率** | 70-85% | 95-100% |
| **速度** | 较快（小数据集） | 快（大数据集） |
| **适用场景** | 离线、原型验证 | 生产环境、复杂查询 |

## 🎯 工作原理

### Enhanced Baseline Agent

1. **LLM 生成过滤条件**
   - 解析用户问题
   - 提取时间范围、品牌、车型等关键词
   - 生成结构化过滤条件

2. **Pandas 数据过滤**
   - 根据过滤条件筛选数据
   - 支持时间范围、品牌、车型等多维度过滤

3. **LLM 分析结果**
   - 将筛选后的数据提供给 LLM
   - LLM 进行聚合、计算、分析
   - 生成自然语言答案

### RAG 版本

1. **文档分块**：将 CSV 文件分成 150 行/块
2. **向量检索**：根据问题关键词检索相关块（top-3）
3. **LLM 计算**：将检索到的数据提供给 LLM 进行分析

## ⚠️ 局限性

- **数据遗漏**：RAG 版本可能遗漏某些数据块
- **计算误差**：LLM 计算大数字可能出错（±5%容差）
- **不稳定性**：同一问题多次查询结果可能略有不同

## 🧪 测试

测试脚本位于 `test/` 目录：

```bash
# 快速测试（前3题）
cd test
python quick_baseline_test.py

# 完整测试（100题）
python run_baseline_test.py
```

详细说明请参考 `test/README.md`。

## 📝 示例问题

```
1. 2023年比亚迪的总销量是多少？
2. 一汽大众在2023年6月的销量同比增长是多少？
3. 2023-12，销量最高的具体车型是哪款？
4. 一汽大众揽境在2023-06的销量是多少？
```

## 🔗 相关文档

- [测试文档](../test/README.md) - 测试脚本使用说明
- [数据脚本文档](data_scripts/README.md) - 数据处理工具说明
- [评估功能说明](../评估功能说明.md) - Gradio 评估功能

---

**提示**：推荐使用 Gradio Web 界面进行测试和对比，可以直观地看到两个 Agent 的性能差异。
