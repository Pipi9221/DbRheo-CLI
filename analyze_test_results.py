"""
分析 Baseline 和 NL2SQL 测试结果
"""
import json

def classify_question(q):
    """分类问题类型"""
    if '每个' in q or '各月' in q or '每个月' in q:
        return '月度汇总'
    elif '总销量' in q or '销量总和' in q or '全年' in q:
        return '总销量'
    elif '同比' in q or '增长' in q:
        return '同比计算'
    elif '环比' in q:
        return '环比计算'
    elif '对比' in q or '哪个' in q or '最高' in q or '最低' in q:
        return '对比/排名'
    elif 'null' in q:
        return 'null答案'
    else:
        return '单点查询'

# 读取 baseline 数据
with open('newtest/baseline/evaluations_20260115_141251.jsonl', 'r', encoding='utf-8') as f:
    baseline = [json.loads(line) for line in f if line.strip()]

# 读取 nl2sql 数据
with open('newtest/nl2sql/evaluations_complete_100.jsonl', 'r', encoding='utf-8') as f:
    nl2sql = [json.loads(line) for line in f if line.strip()]

# 分类统计
baseline_types = {}
nl2sql_types = {}

for r in baseline:
    qtype = classify_question(r['question'])
    baseline_types[qtype] = baseline_types.get(qtype, {'total': 0, 'correct': 0})
    baseline_types[qtype]['total'] += 1
    if r['is_correct']:
        baseline_types[qtype]['correct'] += 1

for r in nl2sql:
    qtype = classify_question(r['question'])
    nl2sql_types[qtype] = nl2sql_types.get(qtype, {'total': 0, 'correct': 0})
    nl2sql_types[qtype]['total'] += 1
    if r['is_correct']:
        nl2sql_types[qtype]['correct'] += 1

print('=' * 80)
print('Baseline 按问题类型分类')
print('=' * 80)
for qtype, stats in sorted(baseline_types.items(), key=lambda x: -x[1]['total']):
    acc = stats['correct'] / stats['total'] * 100 if stats['total'] > 0 else 0
    print(f'{qtype:10s}: {stats["correct"]:3d}/{stats["total"]:3d} ({acc:5.1f}%)')

print('\n' + '=' * 80)
print('NL2SQL 按问题类型分类')
print('=' * 80)
for qtype, stats in sorted(nl2sql_types.items(), key=lambda x: -x[1]['total']):
    acc = stats['correct'] / stats['total'] * 100 if stats['total'] > 0 else 0
    print(f'{qtype:10s}: {stats["correct"]:3d}/{stats["total"]:3d} ({acc:5.1f}%)')

print('\n' + '=' * 80)
print('错误类型分析')
print('=' * 80)

# Baseline 错误原因统计
baseline_errors = {}
for r in baseline:
    if not r['is_correct']:
        reason = r['comparison_reason']
        # 提取错误类型
        if '数值不匹配' in reason:
            err_type = '数值错误'
        elif '百分比不匹配' in reason:
            err_type = '百分比错误'
        elif '文本不匹配' in reason:
            err_type = '文本错误'
        else:
            err_type = reason[:20]
        baseline_errors[err_type] = baseline_errors.get(err_type, 0) + 1

print('\nBaseline 错误类型:')
for err_type, count in sorted(baseline_errors.items(), key=lambda x: -x[1]):
    print(f'  {err_type}: {count} 次')

# NL2SQL 错误原因统计
nl2sql_errors = {}
for r in nl2sql:
    if not r['is_correct']:
        reason = r['comparison_reason']
        if '数值不匹配' in reason:
            err_type = '数值错误'
        elif '百分比不匹配' in reason:
            err_type = '百分比错误'
        elif '文本不匹配' in reason:
            err_type = '文本错误'
        else:
            err_type = reason[:20]
        nl2sql_errors[err_type] = nl2sql_errors.get(err_type, 0) + 1

print('\nNL2SQL 错误类型:')
for err_type, count in sorted(nl2sql_errors.items(), key=lambda x: -x[1]):
    print(f'  {err_type}: {count} 次')
