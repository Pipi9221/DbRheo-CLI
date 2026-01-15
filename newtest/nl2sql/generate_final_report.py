import json
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
eval_file = os.path.join(script_dir, "evaluations_20260115_144535.jsonl")
results = []

with open(eval_file, 'r', encoding='utf-8') as f:
    for line in f:
        results.append(json.loads(line))

total = len(results)
correct = sum(1 for r in results if r['is_correct'])
accuracy = (correct / total * 100) if total > 0 else 0

errors = [r for r in results if not r['is_correct']]

print(f"\n{'='*60}")
print(f"NL2SQL Agent 测试最终报告")
print(f"{'='*60}")
print(f"\n总问题数: {total}")
print(f"正确数量: {correct}")
print(f"错误数量: {len(errors)}")
print(f"准确率: {accuracy:.2f}%")
print(f"\n{'='*60}")
print(f"错误问题列表:")
print(f"{'='*60}")

for i, err in enumerate(errors, 1):
    print(f"\n[{i}] 问题ID: {err['id']}")
    print(f"    问题: {err['question']}")
    print(f"    标准答案: {err['standard_answer']}")
    print(f"    实际答案: {err['actual_answer']}")
    print(f"    原因: {err['comparison_reason']}")

# 写入markdown报告
report_path = os.path.join(script_dir, 'nl2sql_final_report.md')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(f"# NL2SQL Agent 测试最终报告\n\n")
    f.write(f"**测试时间**: 2026-01-15 14:45-15:04\n\n")
    f.write(f"## 测试统计\n\n")
    f.write(f"- 总问题数: {total}\n")
    f.write(f"- 正确数量: {correct}\n")
    f.write(f"- 错误数量: {len(errors)}\n")
    f.write(f"- **准确率: {accuracy:.2f}%**\n\n")
    f.write(f"## 关键发现\n\n")
    f.write(f"1. **Bug修复**: 将turns参数从1改为10，解决了Agent无法完成对话的问题\n")
    f.write(f"2. **测试结果**: 在94个问题中达到{accuracy:.2f}%准确率\n")
    f.write(f"3. **测试中断**: 第95个问题导致进程卡住，已终止\n\n")
    f.write(f"## 错误问题详情\n\n")
    for i, err in enumerate(errors, 1):
        f.write(f"### 错误 {i}: 问题ID {err['id']}\n\n")
        f.write(f"- **问题**: {err['question']}\n")
        f.write(f"- **标准答案**: {err['standard_answer']}\n")
        f.write(f"- **实际答案**: {err['actual_answer']}\n")
        f.write(f"- **原因**: {err['comparison_reason']}\n\n")

print(f"\n报告已保存到: nl2sql_final_report.md")
