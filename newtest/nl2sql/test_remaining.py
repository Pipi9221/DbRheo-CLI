import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../packages/core/src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../packages/cli/src')))

import asyncio
import csv
import json
from datetime import datetime
from dbrheo.core.client import DbRheoClient
from dbrheo.config.base import DatabaseConfig

async def test_question(client, question_id, question, standard_answer):
    """测试单个问题"""
    print(f"\n[{question_id}/100] 测试: {question[:50]}...")
    
    try:
        response = await client.send_message(question, turns=10)
        actual_answer = response.get('content', '').strip()
        
        # 提取答案
        if '【答案：' in actual_answer:
            actual_answer = actual_answer.split('【答案：')[1].split('】')[0].strip()
        
        # 比较答案
        is_correct, reason = compare_answers(standard_answer, actual_answer)
        
        result = {
            'id': question_id,
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'question_fingerprint': ''.join(question.split()),
            'run_number': 1,
            'standard_answer': standard_answer,
            'actual_answer': actual_answer,
            'is_correct': is_correct,
            'comparison_reason': reason,
            'agent_type': 'NL2SQL',
            'full_response': response.get('content', '')
        }
        
        status = "[OK] 正确" if is_correct else "[FAIL] 错误"
        print(f"  {status} | {reason}")
        
        return result
        
    except Exception as e:
        print(f"  [ERROR] 测试失败: {str(e)}")
        return {
            'id': question_id,
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'is_correct': False,
            'comparison_reason': f'测试异常: {str(e)}',
            'agent_type': 'NL2SQL'
        }

def compare_answers(standard, actual):
    """比较答案"""
    if standard == actual:
        return True, f"完全匹配: {standard}"
    
    # 数值比较
    try:
        std_num = float(''.join(c for c in str(standard) if c.isdigit() or c == '.' or c == '-'))
        act_num = float(''.join(c for c in str(actual) if c.isdigit() or c == '.' or c == '-'))
        if abs(std_num - act_num) < 0.01:
            return True, f"数值匹配: {std_num} == {act_num}"
    except:
        pass
    
    return False, f"文本不匹配: '{standard}' != '{actual}'"

async def main():
    # 读取问题和答案
    questions = []
    with open('../../test/question/automotive_questions_list_100.csv', 'r', encoding='utf-8') as f:
        questions = [line.strip() for line in f if line.strip()]
    
    answers = []
    with open('../../test/answer/automotive_answers_100.csv', 'r', encoding='utf-8') as f:
        answers = [line.strip() for line in f if line.strip()]
    
    # 只测试95-100
    start_idx = 94  # 第95个问题（索引94）
    end_idx = 100
    
    # 配置数据库
    db_config = DatabaseConfig(
        db_type="sqlite",
        database="../../db/automotive_sales.db"
    )
    
    # 创建客户端
    client = DbRheoClient(
        model_name="qwen-flash",
        database_config=db_config
    )
    
    results = []
    
    # 测试问题95-100
    for i in range(start_idx, end_idx):
        result = await test_question(client, i+1, questions[i], answers[i])
        results.append(result)
        
        # 保存结果
        with open('evaluations_remaining.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    
    # 统计
    correct = sum(1 for r in results if r['is_correct'])
    print(f"\n{'='*60}")
    print(f"补充测试完成")
    print(f"{'='*60}")
    print(f"测试问题: 95-100 (共6个)")
    print(f"正确: {correct}")
    print(f"错误: {len(results) - correct}")
    print(f"准确率: {correct/len(results)*100:.2f}%")

if __name__ == "__main__":
    asyncio.run(main())
