# 项目文件清理指南

## 📋 可以安全删除的临时文件

### 1. 根目录 - 分析报告文件（临时生成）
这些是分析脚本生成的临时报告文件，可以随时重新生成：

```bash
# 删除命令
del nl2sql_failures_by_time.txt
del nl2sql_failures_report.txt
del untested_questions_report.txt
```

**文件说明：**
- `nl2sql_failures_by_time.txt` - NL2SQL失败分析报告（按时间）
- `nl2sql_failures_report.txt` - NL2SQL失败分析报告
- `untested_questions_report.txt` - 未测试问题报告

### 2. 根目录 - 修复脚本（已完成使命）
这些是一次性修复脚本，修复完成后可以移到scripts目录或删除：

```bash
# 移动到scripts目录（推荐）
move fix_evaluation_answers.py scripts\

# 或直接删除
del fix_evaluation_answers.py
```

**文件说明：**
- `fix_evaluation_answers.py` - 修复评估答案的脚本（已执行完成）

### 3. test/result - 导出的评估文件（旧版本）
保留最新的导出文件即可，旧版本可以删除：

```bash
# 进入目录
cd test\result

# 保留最新的，删除旧的
del evaluation_export_20260115_030744.csv
del evaluation_export_20260115_031201.xlsx
del evaluation_export_20260115_031209.csv
del evaluation_export_20260115_031221.xlsx

# 保留：
# - evaluation_export_20260115_101112.xlsx (最新)
# - evaluations.jsonl (主数据文件)
# - evaluations.jsonl.bak (备份)
```

### 4. 日志文件（可选清理）
日志文件会持续增长，可以定期清理：

```bash
# 根目录日志
del dbrheo.log

# CLI日志
del packages\cli\dbrheo_realtime.log
```

### 5. 缓存目录（可选清理）
Python缓存和临时目录：

```bash
# Python缓存
rmdir /s /q __pycache__

# 旧的评估数据目录（已迁移到test/result）
rmdir /s /q .gradio_evaluations

# Gradio历史记录（如果不需要）
# rmdir /s /q .gradio_history
```

---

## ⚠️ 不要删除的重要文件

### 核心功能文件
- `gradio_app.py` - Gradio Web界面（主应用）
- `analyze_nl2sql_failures.py` - NL2SQL失败分析工具
- `analyze_nl2sql_failures_by_time.py` - 按时间分析失败
- `analyze_untested_questions.py` - 未测试问题分析

### 文档文件
- `README.md` - 项目说明
- `方案设计.md` - 方案设计文档
- `评估功能使用说明.md` - 评估功能说明
- `NL2SQL问题分析.md` - 问题分析文档

### 配置文件
- `.env` - 环境变量（包含API密钥）
- `.env.example` - 环境变量示例
- `.dbrheo.json` - DbRheo配置
- `log_config.yaml` - 日志配置
- `pyproject.toml` - 项目配置
- `requirements.txt` - Python依赖

### 数据文件
- `test/result/evaluations.jsonl` - 评估数据（主文件）
- `test/result/evaluations.jsonl.bak` - 评估数据备份
- `test/result/evaluation_export_20260115_101112.xlsx` - 最新导出

---

## 🔧 清理脚本

创建一个批处理文件来自动清理：

```batch
@echo off
echo 开始清理临时文件...

REM 删除分析报告
del /q nl2sql_failures_by_time.txt 2>nul
del /q nl2sql_failures_report.txt 2>nul
del /q untested_questions_report.txt 2>nul

REM 删除日志
del /q dbrheo.log 2>nul
del /q packages\cli\dbrheo_realtime.log 2>nul

REM 删除Python缓存
rmdir /s /q __pycache__ 2>nul

REM 删除旧的评估导出（保留最新）
cd test\result
del /q evaluation_export_20260115_030744.csv 2>nul
del /q evaluation_export_20260115_031201.xlsx 2>nul
del /q evaluation_export_20260115_031209.csv 2>nul
del /q evaluation_export_20260115_031221.xlsx 2>nul
cd ..\..

echo 清理完成！
pause
```

保存为 `cleanup.bat` 并运行。

---

## 📊 清理后的项目结构

```
DbRheo-CLI/
├── gradio_app.py                    # 主应用
├── analyze_*.py                     # 分析工具
├── README.md                        # 文档
├── 方案设计.md
├── 评估功能使用说明.md
├── NL2SQL问题分析.md
├── .env                             # 配置
├── pyproject.toml
├── requirements.txt
├── baseline/                        # Baseline方案
├── db/                              # 数据库
├── packages/                        # 核心包
├── scripts/                         # 工具脚本
│   ├── fix_*.py                    # 修复脚本（归档）
│   └── README.md
├── test/                            # 测试
│   ├── result/
│   │   ├── evaluations.jsonl       # 主数据
│   │   ├── evaluations.jsonl.bak   # 备份
│   │   └── evaluation_export_*.xlsx # 最新导出
│   ├── answer/
│   ├── question/
│   └── *.py
└── logs/                            # 日志目录
```

---

## 💡 建议

1. **定期清理**：每周清理一次日志和临时报告
2. **备份重要数据**：清理前备份 `test/result/evaluations.jsonl`
3. **版本控制**：使用 `.gitignore` 忽略临时文件
4. **自动化**：使用 `cleanup.bat` 脚本自动清理

---

## 📝 .gitignore 建议

确保以下内容在 `.gitignore` 中：

```gitignore
# 日志文件
*.log
dbrheo.log

# 分析报告
*_report.txt
*_failures*.txt

# Python缓存
__pycache__/
*.pyc

# 临时目录
.gradio_evaluations/
.gradio_history/

# 导出文件（保留最新即可）
test/result/evaluation_export_*.csv
test/result/evaluation_export_*.xlsx

# 环境变量
.env
```
