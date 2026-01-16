# DbRheo-CLI - 自然语言数据库查询系统

## 📋 项目简介

DbRheo-CLI 是一个基于大语言模型的自然语言数据库查询系统，支持通过自然语言进行数据库操作、数据分析和可视化。

**核心特性**：
- 🗣️ 自然语言转 SQL 查询
- 🔍 智能数据库结构探索
- 🐍 Python 代码执行与数据分析
- 📊 数据可视化支持
- 🌐 Web 界面（Gradio）
- 🔒 SQL 风险评估与安全检查
- ✅ 智能答案提取与比较（支持多实体、时间序列）

## 🚀 快速开始

### 1. 环境要求

- Python 3.9+
- SQLite / MySQL / PostgreSQL

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置 API 密钥：

```bash
# LLM API 配置（选择其一）
GOOGLE_API_KEY=your_google_api_key
OPENAI_API_KEY=your_openai_api_key

# 数据库连接（可选）
DATABASE_URL=sqlite:///db/vehicle_sales.db
```

### 4. 启动方式

**方式1：Gradio Web 界面**（推荐）

```bash
python gradio_app.py
```

访问 `http://localhost:7860` 使用 Web 界面。

**方式2：命令行界面**

```bash
cd packages/cli
python cli.py
```

## 📁 项目结构

```
DbRheo-CLI/
├── README.md                    # 本文件
├── gradio_app.py                # Gradio Web 应用
├── requirements.txt             # Python 依赖
├── .env.example                 # 环境变量模板
├── log_config.yaml              # 日志配置
├── packages/                    # 核心代码包
│   ├── core/                    # 核心功能模块
│   │   └── src/dbrheo/
│   │       ├── core/            # 核心逻辑（chat, memory, prompts）
│   │       ├── services/        # LLM 服务（OpenAI, Claude, Gemini）
│   │       ├── adapters/        # 数据库适配器
│   │       ├── tools/           # 工具集（SQL, 文件读写等）
│   │       └── config/          # 配置管理
│   ├── cli/                     # 命令行界面
│   │   └── src/dbrheo_cli/
│   │       ├── app/             # CLI 应用
│   │       ├── handlers/        # 事件处理器
│   │       └── ui/              # 用户界面组件
│   └── web/                     # Web 前端（React）
├── baseline/                    # Baseline Agent（对比实验）
│   ├── README.md                # Baseline 说明文档
│   ├── baseline_agent_enhanced.py  # 主要实现
│   ├── 数据源_销量.csv           # 数据文件
│   └── data_scripts/            # 数据处理脚本
├── test/                        # 测试文件
│   ├── README.md                # 测试文档
│   ├── run_baseline_test.py     # Baseline 测试
│   ├── run_benchmark.py         # Benchmark 测试
│   ├── test_evaluation.py       # 评估功能测试
│   ├── question/                # 测试问题集
│   ├── answer/                  # 标准答案
│   └── result/                  # 测试结果
├── newtest/                     # 新测试框架
│   ├── nl2sql/                  # NL2SQL Agent 测试
│   │   ├── batch_test.py        # 批量测试脚本（含智能答案提取）
│   │   ├── test_fixed_comparator.py # 答案比较器测试
│   │   ├── reevaluate_results.py    # 重新评估测试结果
│   │   ├── evaluations_*.jsonl  # 测试结果
│   │   └── nl2sql_test_report.md # 测试报告
│   └── baseline/                # Baseline Agent 测试
├── scripts/                     # 工具脚本
│   └── fix_*.py                 # 修复脚本
├── db/                          # 数据库文件
│   ├── SCHEMA.md                # 数据库结构说明
│   └── vehicle_sales.db         # SQLite 数据库
└── logs/                        # 日志目录
```

## 🎯 主要功能

### 1. 自然语言查询

```
用户：2023年比亚迪的总销量是多少？
系统：[生成 SQL] SELECT SUM(sales_volume) FROM vehicle_sales WHERE brand='比亚迪' AND date LIKE '2023%'
系统：[执行查询] 结果：150000 辆
```

### 2. 数据分析

```
用户：分析一下2023年各品牌的销量趋势
系统：[生成 Python 代码] 
      import pandas as pd
      import matplotlib.pyplot as plt
      # 查询数据并生成图表
系统：[执行代码] 已生成图表：sales_trend.png
```

### 3. 智能对话

- 支持多轮对话，记忆上下文
- 自动理解用户意图
- 提供数据洞察和建议

## 🌐 Gradio Web 界面

### 功能标签页

1. **💬 NL2SQL Agent** - 自然语言查询
   - 自然语言输入
   - SQL 生成与执行
   - 结果展示
   - 交互流程日志

2. **🔍 SQL 执行** - 直接执行 SQL
   - SQL 语句编辑
   - 示例查询
   - 结果展示

3. **📊 数据库结构** - 查看表结构
   - 表名和字段信息
   - 数据类型

4. **⚡ 快速查询** - 常用查询示例
   - 一键执行预设查询
   - 快速验证功能

5. **📈 Baseline Agent** - 对比实验
   - 基于 CSV 的查询方案
   - 用于性能对比
   - Token 消耗统计

6. **📊 评估结果** - 性能评估与分析
   - 准确率看板（按方案分类）
   - 失败原因分析（饼图）
   - NL2SQL vs Baseline 对比（柱状图）
   - 评估记录查看与导出
   - 问题详情查看（多次运行记录）

7. **📚 历史会话** - 对话历史管理
   - 查看历史会话
   - 加载历史对话
   - 删除会话

### 评估功能

- ✅ 自动答案提取与比较
- ✅ 按 Agent 类型分类统计
- ✅ 导出 CSV/Excel 报告
- ✅ 可视化图表（饼图、柱状图）
- ✅ 问题搜索与筛选
- ✅ 多次运行记录追踪
- ✅ 数据持久化（test/result/evaluations.jsonl）

**智能答案提取与比较**：
- 支持多实体对比答案（如"一汽大众: 9533 辆, 比亚迪: 31140 辆"）
- 支持时间序列答案（如"1月: 4890辆; 2月: 3217辆; ..."）
- 支持百分比答案（容差 0.01%）
- 支持数值型答案（精确匹配）
- 支持文本型答案（完全匹配）
- 允许顺序差异和格式差异（如"辆"单位的有无）

## 🧪 测试与评估

### 运行测试

**旧测试框架 (test/)**

```bash
cd test

# 环境验证
python verify_test_setup.py

# 快速测试（前3题）
python quick_baseline_test.py

# 完整测试（100题）
python run_baseline_test.py

# Benchmark 测试
python run_benchmark.py
```

**新测试框架 (newtest/)**

```bash
cd newtest/nl2sql

# 运行批量测试
python batch_test.py

# 测试修复后的比较器
python test_fixed_comparator.py

# 重新评估测试结果
python reevaluate_results.py
```

详细说明请参考：
- [test/README.md](test/README.md) - 旧测试框架文档
- [newtest/nl2sql/nl2sql_test_report.md](newtest/nl2sql/nl2sql_test_report.md) - 新测试框架报告

## 📊 Baseline 对比实验

Baseline Agent 是一个基于 CSV 文件的查询方案，用于与 DbRheo NL2SQL Agent 进行性能对比。

**对比结果**：
- Baseline Agent：70-85% 准确率
- DbRheo NL2SQL Agent：95-100% 准确率
- 智能答案提取支持多实体对比、时间序列等复杂答案格式

详细说明请参考：
- [baseline/README.md](baseline/README.md) - Baseline Agent 说明
- [newtest/nl2sql/nl2sql_test_report.md](newtest/nl2sql/nl2sql_test_report.md) - 最新测试报告

## 🔧 配置说明

### 支持的 LLM 服务

- **OpenAI**（GPT-4, GPT-3.5）
- **Google Gemini**
- **Claude**（Anthropic）
- **阿里通义千问**（兼容 OpenAI API）

### 支持的数据库

- **SQLite** - 轻量级，适合开发和测试
- **MySQL** - 生产环境
- **PostgreSQL** - 高级功能支持

### 数据库数据处理策略

项目采用简洁高效的数据处理策略：

1. **数据源拆分**：从原始 CSV 拆分为测试集（月同比/环比）和数据源（销量和市场份额）
2. **表结构拆分**：
   - `vehicle_sales` 表：销量数据（unit='辆'）
   - `market_share` 表：市场份额数据（unit='%'）
3. **品牌和车型解析**：从 display_name 字段自动解析品牌和车型信息
4. **日期格式统一**：使用 Pandas 统一为 YYYY-MM-DD 格式
5. **简单别名映射**：通过 LLM 语义理解处理表述差异

详细说明请参考：
- [数据库结构](db/SCHEMA.md) - 数据库表结构
- [Baseline 数据处理](baseline/data_scripts/README.md) - 数据处理脚本说明

### 日志配置

日志配置文件：`log_config.yaml`

```yaml
logging:
  level: INFO
  file:
    enabled: true
    path: "logs/dbrheo_realtime.log"
    max_size: 10485760  # 10MB
```

## 🛠️ 开发指南

### 安装开发依赖

```bash
# 安装核心包（开发模式）
cd packages/core
pip install -e .

# 安装 CLI 包（开发模式）
cd ../cli
pip install -e .
```

### 运行单元测试

```bash
cd test
python test_evaluation.py
python test_new_features.py
```

### 代码结构

- **core/chat.py** - 对话管理
- **core/prompts.py** - 提示词模板
- **services/** - LLM 服务封装
- **adapters/** - 数据库适配器
- **tools/** - 工具集（SQL、文件操作等）

## 📝 使用示例

### 示例1：基础查询

```
问：2023-06，一汽大众揽境的销量是多少？
答：【答案：4045 辆】
```

### 示例2：聚合查询

```
问：2023年比亚迪的总销量是多少？
答：【答案：150000 辆】
```

### 示例3：同比增长

```
问：一汽大众在2023年6月的销量同比增长是多少？
答：【答案：-11.56%】
```

### 示例4：排名查询

```
问：2023-12，销量最高的具体车型是哪款？
答：【答案：比亚迪秦PLUS】
```

## ⚠️ 注意事项

1. **API 费用**：使用 LLM API 会产生费用，请注意配额
2. **数据安全**：生产环境请配置只读数据库用户
3. **SQL 风险**：系统会自动检测危险 SQL 操作
4. **日志管理**：定期清理日志文件

## 🧹 项目维护

### 数据备份

重要数据文件：
- `test/result/evaluations.jsonl` - 评估数据（主文件）
- `test/result/evaluations.jsonl.bak` - 评估数据备份
- `newtest/nl2sql/evaluations_*.jsonl` - 新测试框架评估数据
- `.env` - 环境变量（包含 API 密钥）

建议定期备份这些文件。

### 清理建议

项目会生成一些临时文件和日志，可定期清理：

**可清理的文件**：
- 分析报告（`*_report.txt`、`*_failures*.txt`）
- 日志文件（`dbrheo.log`、`packages/cli/dbrheo_realtime.log`）
- Python 缓存（`__pycache__/`）
- 旧的评估导出（`test/result/evaluation_export_*.xlsx`）
- 旧的评估目录（`.gradio_evaluations/`）
- 临时测试脚本（如 `temp_fix.py`、`count_chars.py` 等）

## 🔗 相关文档

- [测试文档](test/README.md) - 测试脚本使用说明
- [Baseline 文档](baseline/README.md) - Baseline Agent 说明
- [数据库结构](db/SCHEMA.md) - 数据库表结构
- [评估功能说明](评估功能使用说明.md) - Gradio 评估功能详解
- [方案设计](方案设计.md) - 技术方案设计文档
- [问题分析](NL2SQL问题分析.md) - NL2SQL 问题分析报告
- [NL2SQL 测试报告](newtest/nl2sql/nl2sql_test_report.md) - 新测试框架测试结果

## 📊 分析工具

项目提供了多个分析工具脚本：

```bash
# NL2SQL 失败分析
python analyze_nl2sql_failures.py

# 按时间分析失败
python analyze_nl2sql_failures_by_time.py

# 未测试问题分析
python analyze_untested_questions.py

# 测试结果分析
python analyze_test_results.py

# 新测试框架错误分析
cd newtest/nl2sql
python analyze_errors.py
```

## 📄 许可证

本项目仅供学习和研究使用。

---

**快速开始**：`python gradio_app.py` 🚀

**需要帮助？** 查看 [CLEANUP_GUIDE.md](CLEANUP_GUIDE.md) 了解项目维护
