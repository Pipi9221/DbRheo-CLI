"""
测试修复后的答案比较器
"""
import sys
import json
from pathlib import Path

# 从 batch_test.py 导入 AnswerComparator
sys.path.insert(0, str(Path(__file__).parent))
from batch_test import AnswerComparator

# 创建比较器
comparator = AnswerComparator()

# 测试用例
test_cases = [
    {
        'name': '多实体对比（顺序不同）',
        'standard': '一汽大众: 9533 辆, 比亚迪: 31140 辆',
        'actual': '比亚迪: 31140 辆; 一汽大众: 9533 辆',
        'expected': True,
        'description': '应该识别出实体相同，只是顺序不同'
    },
    {
        'name': '多实体对比（缺失实体）',
        'standard': '一汽大众: 9533 辆, 比亚迪: 31140 辆',
        'actual': '比亚迪: 31140 辆',
        'expected': False,
        'description': '缺少一汽大众数据，应该识别为不匹配'
    },
    {
        'name': '时间序列（完整匹配）',
        'standard': '1月: 4890辆; 2月: 3217辆; 3月: 7370辆',
        'actual': '1月: 4890辆; 2月: 3217辆; 3月: 7370辆',
        'expected': True,
        'description': '时间序列完整匹配'
    },
    {
        'name': '时间序列（单位差异）',
        'standard': '1月: 4890辆; 2月: 3217辆; 3月: 7370辆',
        'actual': '1月: 4890; 2月: 3217; 3月: 7370',
        'expected': True,
        'description': '数值相同，只是单位"辆"缺失，应该匹配'
    },
    {
        'name': '数值型（完全匹配）',
        'standard': '4045 辆',
        'actual': '4045',
        'expected': True,
        'description': '数值匹配，忽略单位差异'
    },
    {
        'name': '数值型（不匹配）',
        'standard': '4045 辆',
        'actual': '4046',
        'expected': False,
        'description': '数值不匹配'
    },
    {
        'name': '百分比（在容差范围内）',
        'standard': '-37.61942154168302%',
        'actual': '-37.61942154168300%',
        'expected': True,
        'description': '百分比在0.01%容差范围内'
    },
    {
        'name': '百分比（超出容差）',
        'standard': '-44.44444444444444%',
        'actual': '-55.55555555555556%',
        'expected': False,
        'description': '百分比超出容差范围'
    },
]

print("=" * 80)
print("测试修复后的 AnswerComparator")
print("=" * 80)

passed = 0
failed = 0

for i, test_case in enumerate(test_cases, 1):
    print(f"\n[{i}/{len(test_cases)}] {test_case['name']}")
    print(f"  描述: {test_case['description']}")
    
    is_correct, reason = comparator.compare_answers(test_case['standard'], test_case['actual'])
    
    expected = test_case['expected']
    if is_correct == expected:
        passed += 1
        print(f"  [PASS] {reason}")
    else:
        failed += 1
        print(f"  [FAIL] 期望: {expected}, 实际: {is_correct}")
        print(f"  {reason}")
    
    print(f"  标准答案: {test_case['standard']}")
    print(f"  实际答案: {test_case['actual']}")

print("\n" + "=" * 80)
print("测试结果")
print("=" * 80)
print(f"通过: {passed}/{len(test_cases)}")
print(f"失败: {failed}/{len(test_cases)}")
print(f"通过率: {passed/len(test_cases)*100:.1f}%")
print("=" * 80)
