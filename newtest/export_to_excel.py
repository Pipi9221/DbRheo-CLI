"""通用Excel导出工具 - 用于nl2sql和baseline测试结果"""
import json
import os
import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def export_to_excel(jsonl_file, output_prefix='test_results'):
    """导出JSONL测试结果到Excel
    
    Args:
        jsonl_file: JSONL文件路径
        output_prefix: 输出文件名前缀
    """
    # 读取结果
    results = []
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            results.append(json.loads(line))
    
    if not results:
        print(f"错误: {jsonl_file} 为空")
        return
    
    # 转换为DataFrame
    df = pd.DataFrame(results)
    
    # 选择关键列
    df_export = df[['id', 'question', 'standard_answer', 'actual_answer', 'is_correct', 'comparison_reason', 'timestamp']]
    df_export.columns = ['问题ID', '问题', '标准答案', '实际答案', '是否正确', '比较原因', '测试时间']
    
    # 生成Excel文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    excel_file = f'{output_prefix}_{timestamp}.xlsx'
    
    # 导出到Excel
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        # 全部结果
        df_export.to_excel(writer, sheet_name='全部结果', index=False)
        
        # 错误结果
        df_errors = df_export[df_export['是否正确'] == False]
        df_errors.to_excel(writer, sheet_name='错误结果', index=False)
        
        # 统计摘要
        total = len(results)
        correct = sum(1 for r in results if r['is_correct'])
        summary = pd.DataFrame({
            '指标': ['总问题数', '正确数量', '错误数量', '准确率'],
            '数值': [total, correct, total - correct, f"{correct/total*100:.2f}%"]
        })
        summary.to_excel(writer, sheet_name='统计摘要', index=False)
    
    print(f"✅ Excel导出成功: {excel_file}")
    print(f"   - 全部结果: {len(df_export)}条")
    print(f"   - 错误结果: {len(df_errors)}条")
    print(f"   - 准确率: {correct/total*100:.2f}%")
    
    return excel_file

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python export_to_excel.py <jsonl文件路径> [输出前缀]")
        print("示例: python export_to_excel.py nl2sql/evaluations_complete_100.jsonl nl2sql_results")
        sys.exit(1)
    
    jsonl_file = sys.argv[1]
    output_prefix = sys.argv[2] if len(sys.argv) > 2 else 'test_results'
    
    if not os.path.exists(jsonl_file):
        print(f"错误: 文件不存在 {jsonl_file}")
        sys.exit(1)
    
    export_to_excel(jsonl_file, output_prefix)
