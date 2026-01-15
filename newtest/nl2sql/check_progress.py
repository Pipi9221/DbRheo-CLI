import json
from pathlib import Path

jsonl_file = Path(__file__).parent / 'evaluations_20260115_144535.jsonl'

with open(jsonl_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

total = len(lines)
correct = sum(1 for line in lines if json.loads(line).get('is_correct', False))

print(f"已完成: {total}/100")
print(f"正确: {correct}")
print(f"准确率: {correct/total*100:.2f}%")
