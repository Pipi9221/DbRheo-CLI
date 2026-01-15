"""
修复评估记录中的标准答案
只更新 Baseline 类型的记录，使用 automotive_answers_100.csv 中的正确答案
"""

import json
import re
from pathlib import Py
from datetime import datetime


def generate_fingerprint(question: str) -> str:
    """生成问题指纹（与 gradio_app.py 中的逻辑一致）"""
    if not question:
        return ""
    
    import string
    translator = str.maketrans('', '', string.punctuation + string.whitespace + '，。！？；：')
    fingerprint = question.translate(translator)
    return fingerprint.lower()


def extract_value(text: str) -> str:
    """从文本中提取关键值"""
    if not text:
        return ""
    
    numbers = re.findall(r'-?\d+\.?\d*%?', text)
    if numbers:
        return numbers[0]
    
    return ' '.join(text.split())


def is_numeric(text: str) -> bool:
    """判断文本是否为数值型"""
    try:
        cleaned = text.rstrip('%')
        float(cleaned)
        return True
    except ValueError:
        return False


def compare_answers(standard_answer: str, actual_answer: str) -> tuple:
    """比较标准答案和实际答案（与 gradio_app.py 中的逻辑一致）"""
    if not standard_answer or not actual_answer:
        return False, "答案为空"
    
    standard_value = extract_value(standard_answer)
    actual_value = extract_value(actual_answer)
    
    # 百分比答案
    if '%' in standard_answer and '%' in actual_answer:
        try:
            std_num = float(standard_value.rstrip('%'))
            act_num = float(actual_value.rstrip('%'))
            if abs(std_num - act_num) <= 5.0:
                return True, f"百分比匹配: {std_num}% ≈ {act_num}%"
            else:
                return False, f"百分比不匹配: {std_num}% vs {act_num}%"
        except ValueError:
            return False, "百分比解析失败"
    
    # 数值型答案
    if is_numeric(standard_value) and is_numeric(actual_value):
        try:
            std_num = float(standard_value)
            act_num = float(actual_value)
            tolerance = abs(std_num) * 0.05 if std_num != 0 else 0
            
            if abs(std_num - act_num) <= tolerance:
                return True, f"数值匹配: {std_num} ≈ {act_num}"
            else:
                return False, f"数值不匹配: {std_num} vs {act_num}"
        except ValueError:
            return False, "数值解析失败"
    
    # 文本型答案
    if standard_value in actual_answer or actual_value in standard_answer:
        return True, f"文本匹配: 包含关系"
    
    if standard_value == actual_value:
        return True, f"完全匹配: {standard_value}"
    
    return False, f"答案不匹配: '{standard_value}' vs '{actual_value}'"


def load_correct_answers(csv_path: Path) -> dict:
    """加载正确答案文件"""
    qa_dict = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        current_question = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("问题："):
                current_question = line.replace("问题：", "").strip()
            elif line.startswith("答案："):
                current_answer = line.replace("答案：", "").strip()
                
                if current_question is not None:
                    fingerprint = generate_fingerprint(current_question)
                    qa_dict[fingerprint] = current_answer
                    current_question = None
    
    return qa_dict


def main():
    # 设置控制台编码为 UTF-8
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    base_dir = Path(__file__).parent
    csv_path = base_dir / "test" / "answer" / "automotive_answers_100.csv"
    eval_path = base_dir / ".gradio_evaluations" / "evaluations.jsonl"
    backup_path = eval_path.with_suffix('.jsonl.backup')
    
    print("=" * 60)
    print("修复评估记录中的标准答案")
    print("=" * 60)
    
    # 1. 加载正确答案
    print(f"\n[1/4] 加载正确答案: {csv_path}")
    qa_dict = load_correct_answers(csv_path)
    print(f"✓ 加载了 {len(qa_dict)} 个问题答案")
    
    # 2. 读取评估记录
    print(f"\n[2/4] 读取评估记录: {eval_path}")
    evaluations = []
    with open(eval_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                evaluations.append(json.loads(line))
    print(f"✓ 读取了 {len(evaluations)} 条评估记录")
    
    # 3. 更新 Baseline 记录
    print(f"\n[3/4] 更新 Baseline 记录...")
    updated_count = 0
    matched_count = 0
    corrected_count = 0
    
    for eval_record in evaluations:
        if eval_record.get('agent_type') == 'Baseline':
            fingerprint = eval_record.get('question_fingerprint', '')
            
            # 查找正确答案
            if fingerprint in qa_dict:
                matched_count += 1
                correct_answer = qa_dict[fingerprint]
                old_answer = eval_record.get('standard_answer', '')
                
                # 只有当答案不同时才更新
                if old_answer != correct_answer:
                    updated_count += 1
                    eval_record['standard_answer'] = correct_answer
                    
                    # 重新判断是否正确
                    actual_answer = eval_record.get('actual_answer', '')
                    is_correct, reason = compare_answers(correct_answer, actual_answer)
                    
                    old_correct = eval_record.get('is_correct', False)
                    eval_record['is_correct'] = is_correct
                    eval_record['comparison_reason'] = reason
                    
                    if old_correct != is_correct:
                        corrected_count += 1
                        print(f"  - 问题 #{eval_record['id']}: {eval_record['question'][:40]}...")
                        print(f"    旧答案: {old_answer[:50]}")
                        print(f"    新答案: {correct_answer[:50]}")
                        print(f"    判断: {old_correct} -> {is_correct}")
    
    print(f"\n✓ 匹配到 {matched_count} 条 Baseline 记录")
    print(f"✓ 更新了 {updated_count} 条记录的标准答案")
    print(f"✓ 修正了 {corrected_count} 条记录的正确性判断")
    
    # 4. 备份并保存
    print(f"\n[4/4] 保存结果...")
    
    # 备份原文件
    if eval_path.exists():
        import shutil
        shutil.copy2(eval_path, backup_path)
        print(f"✓ 备份原文件: {backup_path}")
    
    # 写入新文件
    with open(eval_path, 'w', encoding='utf-8') as f:
        for eval_record in evaluations:
            f.write(json.dumps(eval_record, ensure_ascii=False) + '\n')
    print(f"✓ 保存新文件: {eval_path}")
    
    print("\n" + "=" * 60)
    print("✅ 完成！")
    print("=" * 60)
    print(f"\n统计信息：")
    print(f"  - 总记录数: {len(evaluations)}")
    print(f"  - Baseline 记录: {matched_count}")
    print(f"  - 更新答案: {updated_count}")
    print(f"  - 修正判断: {corrected_count}")
    print(f"\n备份文件: {backup_path}")


if __name__ == "__main__":
    main()
