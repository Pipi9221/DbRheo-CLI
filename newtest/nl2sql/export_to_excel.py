"""导出测试结果到Excel"""
import json
import os
import sys
import pandas as pd
from datetime import datetime

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# 读取完整结果
results = []
with open('evaluations_complete_100.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        results.append(json.loads(line))

# 转换为DataFrame
df = pd.DataFrame(results)

# 选择关键列
df_export = df[['id', 'question', 'standard_answer', 'actual_answer', 'is_correct', 'comparison_reason', 'timestamp']]

# 重命名列
df_export.columns = ['问题ID', '问题', '标准答案', '实际答案', '是否正确', '比较原因', '测试时间']

# 导出到Excel
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
excel_file = f'nl2sql_test_results_{timestamp}.xlsx'

with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
    # 全部结果
    df_export.to_excel(writer, sheet_name='全部结果', index=False)
    
    # 错误结果
    df_errors = df_export[df_export['是否正确'] == False]
    df_errors.to_excel(writer, sheet_name='错误结果', index=False)
    
    # 统计摘要
    summary = pd.DataFrame({
        '指标': ['总问题数', '正确数量', '错误数量', '准确率'],
        '数值': [
            len(results),
            sum(1 for r in results if r['is_correct']),
            sum(1 for r in results if not r['is_correct']),
            f"{sum(1 for r in results if r['is_correct'])/len(results)*100:.2f}%"
        ]
    })
    summary.to_excel(writer, sheet_name='统计摘要', index=False)

print(f"✅ Excel导出成功: {excel_file}")
print(f"   - 全部结果: {len(df_export)}条")
print(f"   - 错误结果: {len(df_errors)}条")
print(f"   - 准确率: {sum(1 for r in results if r['is_correct'])/len(results)*100:.2f}%")
