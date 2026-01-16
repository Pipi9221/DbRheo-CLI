"""
分析测试结果中的错误类型
"""
import json

with open('evaluations_complete_100.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 统计错误类型
errors = []
for line in lines:
    record = json.loads(line)
    if not record['is_correct']:
        errors.append({
            'id': record['id'],
            'question': record['question'],
            'standard': record['standard_answer'],
            'actual': record['actual_answer'],
            'reason': record['comparison_reason']
        })

print(f'总错误数: {len(errors)}')
print()
print('错误列表:')
for i, err in enumerate(errors[:20], 1):
    print(f'{i}. 问题{err["id"]}: {err["reason"]}')
    print(f'   标准答案: {err["standard"]}')
    print(f'   实际答案: {err["actual"]}')
    print()

# 统计错误类型分布
error_types = {}
for err in errors:
    reason = err['reason']
    if '数值不匹配' in reason:
        error_type = '数值不匹配'
    elif '百分比不匹配' in reason:
        error_type = '百分比不匹配'
    elif '文本不匹配' in reason:
        error_type = '文本不匹配'
    else:
        error_type = '其他'
    error_types[error_type] = error_types.get(error_type, 0) + 1

print('\n错误类型分布:')
for error_type, count in sorted(error_types.items()):
    print(f'  {error_type}: {count}')
