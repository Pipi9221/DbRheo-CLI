"""
批量测试 Baseline Agent 脚本
将结果保存到 evaluations.jsonl 格式
"""

import sys
import os
import json
import re
from datetime import datetime
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

# 添加路径 - 从 newtest/baseline 目录回到项目根目录
script_dir = Path(__file__).parent
# newtest/baseline -> newtest -> DbRheo-CLI (项目根目录)
project_root = script_dir.parent.parent

sys.path.insert(0, str(project_root / 'baseline'))

from baseline_agent_enhanced import EnhancedBaselineAgent


class AnswerComparator:
    """答案比较器"""
    
    def compare_answers(self, standard_answer: str, actual_answer: str) -> tuple[bool, str]:
        """比较标准答案和实际答案是否正确
        
        比较规则：
        1. 百分比答案：小数点后14位精度，误差<=0.01%
        2. 数值答案：值必须完全相等
        3. 文本答案：必须完全匹配
        
        Returns:
            (is_correct, reason): 是否正确和原因说明
        """
        if not standard_answer or not actual_answer:
            return False, "答案为空"

        # 提取标准答案和实际答案的值
        standard_value = self._extract_value(standard_answer)
        actual_value = self._extract_value(actual_answer)

        # 类型1：百分比答案（如 -11.56069364161850%）
        if '%' in standard_answer and '%' in actual_answer:
            try:
                std_num = float(standard_value.rstrip('%'))
                act_num = float(actual_value.rstrip('%'))
                
                # 计算绝对误差
                abs_error = abs(std_num - act_num)
                
                # 允许的误差范围：0.01%
                tolerance = 0.01
                
                if abs_error <= tolerance:
                    return True, f"百分比匹配: {std_num:.14f}% ≈ {act_num:.14f}%"
                else:
                    return False, f"百分比不匹配: {std_num:.14f}% vs {act_num:.14f}% (误差: {abs_error:.14f}%)"
            except ValueError:
                return False, "百分比解析失败"

        # 类型2：数值型答案 - 必须完全相等
        if self._is_numeric(standard_value) and self._is_numeric(actual_value):
            try:
                std_num = float(standard_value)
                act_num = float(actual_value)
                
                # 数值必须完全相等
                if std_num == act_num:
                    return True, f"数值匹配: {std_num} == {act_num}"
                else:
                    return False, f"数值不匹配: {std_num} != {act_num}"
            except ValueError:
                return False, "数值解析失败"

        # 类型3：文本型答案 - 必须完全匹配
        if standard_value == actual_value:
            return True, f"文本完全匹配: {standard_value}"
        else:
            return False, f"文本不匹配: '{standard_value}' != '{actual_value}'"

    def _extract_value(self, text: str) -> str:
        """从文本中提取关键值"""
        if not text:
            return ""

        # 提取数字（可能带百分比）
        numbers = re.findall(r'-?\d+\.?\d*%?', text)
        if numbers:
            return numbers[0]

        # 如果没有数字，返回清理后的文本
        return text.strip()

    def _is_numeric(self, text: str) -> bool:
        """判断文本是否为数值型"""
        try:
            # 去掉百分比符号
            cleaned = text.rstrip('%')
            float(cleaned)
            return True
        except ValueError:
            return False


def generate_fingerprint(question: str) -> str:
    """生成问题指纹（用于识别同一问题）"""
    if not question:
        return ""

    # 去除所有空格、标点、特殊字符
    import string
    translator = str.maketrans('', '', string.punctuation + string.whitespace + '，。！？；：')
    fingerprint = question.translate(translator)

    # 统一为小写
    fingerprint = fingerprint.lower()

    return fingerprint


def extract_answer(response: str) -> str:
    """从完整响应中提取答案"""
    if not response:
        return ""

    # 查找【答案：...】格式
    match = re.search(r'【答案：(.*?)】', response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 查找【答案：...（无右括号）
    match = re.search(r'【答案：(.*?)$', response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 如果没有找到，尝试查找最后一行
    lines = response.strip().split('\n')
    for line in reversed(lines):
        line = line.strip()
        if line and not line.startswith('[') and not line.startswith('('):
            return line

    return ""


def load_questions_and_answers(questions_file: str, answers_file: str):
    """加载问题和标准答案
    
    Returns:
        list of (question, standard_answer) tuples
    """
    # 读取问题文件
    with open(questions_file, 'r', encoding='utf-8') as f:
        questions = f.readlines()

    # 读取答案文件
    with open(answers_file, 'r', encoding='utf-8') as f:
        answers = f.readlines()

    # 解析并配对
    qa_pairs = []
    
    # 解析答案文件（支持带编号和不带编号两种格式）
    current_question = None
    current_answer = None
    
    for line in answers:
        line = line.strip()
        if not line:
            continue
        
        # 处理带编号的格式：1. 问题：xxx
        if re.match(r'^\d+\.\s*问题：', line):
            # 保存上一个问答对（如果有）
            if current_question and current_answer:
                qa_pairs.append((current_question, current_answer))
            # 去除编号部分
            current_question = re.sub(r'^\d+\.\s*', '', line).replace('问题：', '')
            current_answer = None
        # 处理不带编号的格式：问题：xxx
        elif line.startswith('问题：'):
            # 保存上一个问答对（如果有）
            if current_question and current_answer:
                qa_pairs.append((current_question, current_answer))
            current_question = line.replace('问题：', '')
            current_answer = None
        elif line.startswith('答案：'):
            current_answer = line.replace('答案：', '')

    # 添加最后一个问答对
    if current_question and current_answer:
        qa_pairs.append((current_question, current_answer))

    return qa_pairs


def run_baseline_batch_test(
    csv_path: str,
    questions_file: str,
    answers_file: str,
    output_file: str,
    skip_existing: bool = True,
    question_indices: list[int] = None
):
    """批量测试 Baseline Agent
    
    Args:
        csv_path: CSV 数据文件路径
        questions_file: 问题文件路径
        answers_file: 答案文件路径
        output_file: 输出文件路径
        skip_existing: 是否跳过已存在的问题
        question_indices: 要测试的问题序号列表（1-based索引），如 [1, 3, 5] 或 range(1, 10)
    """
    print("=" * 80)
    print("批量测试 Baseline Agent")
    print("=" * 80)
    print(f"数据文件: {csv_path}")
    print(f"问题文件: {questions_file}")
    print(f"答案文件: {answers_file}")
    print(f"输出文件: {output_file}")
    print(f"跳过已存在: {skip_existing}")
    if question_indices:
        print(f"测试序号: {question_indices}")
    print("=" * 80)

    # 初始化 Agent
    print("\n[1/4] 初始化 Baseline Agent...")
    agent = EnhancedBaselineAgent(csv_path)
    comparator = AnswerComparator()

    # 加载问题和答案
    print("\n[2/4] 加载问题和标准答案...")
    qa_pairs = load_questions_and_answers(questions_file, answers_file)
    total_questions = len(qa_pairs)
    print(f"加载了 {total_questions} 个问题")

    # 根据序号筛选问题
    if question_indices:
        # 过滤出有效的问题序号
        valid_indices = [i for i in question_indices if 1 <= i <= total_questions]
        if len(valid_indices) != len(question_indices):
            invalid = set(question_indices) - set(valid_indices)
            print(f"警告：以下序号超出范围（1-{total_questions}），已跳过: {invalid}")

        # 筛选出指定序号的问题
        filtered_qa_pairs = []
        for i in valid_indices:
            filtered_qa_pairs.append(qa_pairs[i - 1])
        qa_pairs = filtered_qa_pairs
        print(f"筛选后测试 {len(qa_pairs)} 个问题（序号: {valid_indices}）")

    # 创建输出目录
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 批量测试
    print("\n[3/4] 开始批量测试...")
    print("-" * 80)

    success_count = 0
    fail_count = 0

    for idx, (question, standard_answer) in enumerate(qa_pairs, 1):
        print(f"\n[{idx}/{len(qa_pairs)}] 测试: {question[:60]}...")
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                print(f"  [RETRY {attempt}/{max_retries}] 重试中...")
            
            try:
                # 使用线程池执行带超时的查询
                with ThreadPoolExecutor() as executor:
                    future = executor.submit(agent.query, question)
                    try:
                        response_dict = future.result(timeout=60)
                    except TimeoutError:
                        if attempt < max_retries:
                            print(f"  [TIMEOUT] 超时(60秒)，将重试...")
                            continue
                        else:
                            print(f"  [TIMEOUT] 超时，已达最大重试次数")
                            response_dict = {'answer': '[TIMEOUT] 查询超时(60秒)'}
                
                actual_answer = extract_answer(response_dict['answer'])

                # 比较答案
                is_correct, reason = comparator.compare_answers(standard_answer, actual_answer)

                # 构造评估记录
                evaluation = {
                    'id': idx,
                    'timestamp': datetime.now().isoformat(),
                    'question': question,
                    'question_fingerprint': generate_fingerprint(question),
                    'run_number': attempt,
                    'standard_answer': standard_answer,
                    'actual_answer': actual_answer,
                    'is_correct': is_correct,
                    'comparison_reason': reason,
                    'agent_type': 'Baseline',
                    'full_response': response_dict['answer'],
                    'filtered_rows': response_dict.get('filtered_rows', 0),
                    'tokens': response_dict.get('tokens'),
                    'duration_ms': response_dict.get('duration_ms')
                }

                # 保存到文件
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(evaluation, ensure_ascii=False) + '\n')

                # 统计
                if is_correct:
                    success_count += 1
                    print(f"  ✓ 正确 | {reason}")
                else:
                    fail_count += 1
                    print(f"  ✗ 错误 | {reason}")
                    print(f"    标准答案: {standard_answer}")
                    print(f"    实际答案: {actual_answer}")
                
                break  # 成功完成，跳出重试循环

            except Exception as e:
                if attempt < max_retries:
                    print(f"  [ERROR] 异常: {e}，将重试...")
                    continue
                else:
                    fail_count += 1
                    print(f"  [ERROR] 异常: {e}，已达最大重试次数")
                    import traceback
                    traceback.print_exc()

    # 输出统计
    print("\n[4/4] 测试完成")
    print("-" * 80)
    print(f"总问题数: {total_questions}")
    if question_indices:
        print(f"指定序号: {question_indices}")
    print(f"实际测试: {len(qa_pairs)} 个问题")
    print(f"成功数量: {success_count}")
    print(f"失败数量: {fail_count}")
    if success_count + fail_count > 0:
        accuracy = success_count / (success_count + fail_count) * 100
        print(f"准确率: {accuracy:.2f}%")
    print("-" * 80)
    print(f"结果已保存到: {output_file}")


if __name__ == '__main__':
    # 配置路径 - 使用脚本顶部已定义好的 project_root（指向项目根目录）
    csv_path = str(project_root / 'baseline' / '数据源_销量.csv')
    questions_file = str(project_root / 'test' / 'question' / 'automotive_questions_list_100.csv')
    answers_file = str(project_root / 'test' / 'answer' / 'automotive_answers_100.csv')

    # 生成时间戳文件名（每次测试创建独立文件）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = str(Path(__file__).parent / f'evaluations_{timestamp}.jsonl')

    # 运行批量测试 - 完整测试所有问题
    run_baseline_batch_test(
        csv_path=csv_path,
        questions_file=questions_file,
        answers_file=answers_file,
        output_file=output_file,
        skip_existing=False,  # 不跳过，每次都是完整测试
        question_indices=None  # None 表示测试所有1-100个问题
    )
