# 测试工具使用说明

## 目录结构

```
newtest/
├── export_to_excel.py          # 通用Excel导出工具
├── baseline/                   # Baseline测试
│   ├── batch_test.py          # 批量测试脚本
│   └── evaluations.jsonl      # 测试结果
└── nl2sql/                    # NL2SQL测试
    ├── batch_test.py          # 批量测试脚本
    └── evaluations_complete_100.jsonl  # 完整测试结果
```

## Excel导出工具

### 功能
将JSONL格式的测试结果导出为Excel文件，包含3个工作表：
- **全部结果**: 所有测试记录
- **错误结果**: 仅错误的测试记录
- **统计摘要**: 准确率统计

### 使用方法

```bash
# 基本用法
python export_to_excel.py <jsonl文件路径> [输出前缀]

# 导出NL2SQL结果
python export_to_excel.py nl2sql/evaluations_complete_100.jsonl nl2sql_results

# 导出Baseline结果
python export_to_excel.py baseline/evaluations.jsonl baseline_results
```

### 输出示例
```
✅ Excel导出成功: nl2sql_results_20260115_152507.xlsx
   - 全部结果: 100条
   - 错误结果: 12条
   - 准确率: 88.00%
```

## 测试结果对比

| 方法 | 准确率 | 正确数 | 错误数 |
|------|--------|--------|--------|
| NL2SQL Agent | 88.00% | 88/100 | 12 |
| Baseline | 82.00% | 82/100 | 18 |

**NL2SQL Agent 比 Baseline 提升了 6%**
