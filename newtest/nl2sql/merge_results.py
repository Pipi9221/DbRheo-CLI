"""合并测试结果"""
import json
import os
from pathlib import Path

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

# 读取原有94个结果
results = []
with open('evaluations_20260115_144535.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        results.append(json.loads(line))

# 读取新的6个结果
with open('evaluations_95_100.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        result = json.loads(line)
        # 调整ID为95-100
        result['id'] = 94 + result['id']
        results.append(result)

# 按ID排序
results.sort(key=lambda x: x['id'])

# 保存完整结果
with open('evaluations_complete_100.jsonl', 'w', encoding='utf-8') as f:
    for r in results:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')

# 统计
total = len(results)
correct = sum(1 for r in results if r['is_correct'])
accuracy = correct / total * 100

print(f"合并完成！")
print(f"总问题数: {total}")
print(f"正确数量: {correct}")
print(f"准确率: {accuracy:.2f}%")
print(f"结果已保存到: evaluations_complete_100.jsonl")
