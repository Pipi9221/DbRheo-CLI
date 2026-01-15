"""测试问题95-100"""
import sys
import os
from pathlib import Path
import asyncio

script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))

# 导入batch_test的函数
from batch_test import run_nl2sql_batch_test
from datetime import datetime

if __name__ == '__main__':
    questions_file = str(project_root / 'test' / 'question' / 'automotive_questions_list_100.csv')
    answers_file = str(project_root / 'test' / 'answer' / 'automotive_answers_100.csv')
    output_file = str(script_dir / 'evaluations_95_100.jsonl')

    # 只测试问题95-100
    asyncio.run(run_nl2sql_batch_test(
        questions_file=questions_file,
        answers_file=answers_file,
        output_file=output_file,
        skip_existing=False,
        question_indices=[95, 96, 97, 98, 99, 100]
    ))
