"""
批量测试 NL2SQL Agent 脚本
将结果保存到 evaluations.jsonl 格式

核心设计：
- 每个查询使用独立的 session_id，避免上下文干扰
- 每次查询都是新对话，不保留历史上下文
- 适用于批量测试场景，确保每个问题的独立性
"""

import sys
import os
import json
import re
from datetime import datetime
from pathlib import Path
import asyncio

# 设置标准输出编码为 UTF-8，避免 Windows GBK 编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv(str(Path(__file__).parent.parent.parent / '.env'))
except ImportError:
    print("警告: python-dotenv 未安装，跳过 .env 文件加载")
except Exception as e:
    print(f"警告: 加载 .env 文件失败: {e}")

# 添加路径 - 从 newtest/nl2sql 目录回到项目根目录
script_dir = Path(__file__).parent
# newtest/nl2sql -> newtest -> DbRheo-CLI (项目根目录)
project_root = script_dir.parent.parent

sys.path.insert(0, str(project_root / 'packages' / 'core' / 'src'))
sys.path.insert(0, str(project_root / 'packages' / 'cli' / 'src'))

from dbrheo.adapters.connection_manager import DatabaseConnectionManager
from dbrheo.config.base import DatabaseConfig


class AnswerComparator:
    """答案比较器"""
    
    def compare_answers(self, standard_answer: str, actual_answer: str) -> tuple[bool, str]:
        """比较标准答案和实际答案是否正确"""
        if not standard_answer or not actual_answer:
            return False, "答案为空"
        
        # 特殊处理：多实体对比答案
        if ';' in standard_answer or ';' in actual_answer:
            return self._compare_multi_entity_answer(standard_answer, actual_answer)

        # 特殊处理：时间序列答案（多个值）
        if self._is_time_series(standard_answer) or self._is_time_series(actual_answer):
            return self._compare_time_series_answer(standard_answer, actual_answer)

        standard_value = self._extract_value(standard_answer)
        actual_value = self._extract_value(actual_answer)

        # 类型1：百分比答案
        if '%' in standard_answer and '%' in actual_answer:
            try:
                std_num = float(standard_value.rstrip('%'))
                act_num = float(actual_value.rstrip('%'))
                abs_error = abs(std_num - act_num)
                tolerance = 0.01
                
                if abs_error <= tolerance:
                    return True, f"百分比匹配: {std_num:.14f}% ≈ {act_num:.14f}%"
                else:
                    return False, f"百分比不匹配: {std_num:.14f}% vs {act_num:.14f}% (误差: {abs_error:.14f}%)"
            except ValueError:
                return False, "百分比解析失败"

        # 类型2：数值型答案
        if self._is_numeric(standard_value) and self._is_numeric(actual_value):
            try:
                std_num = float(standard_value)
                act_num = float(actual_value)
                
                if std_num == act_num:
                    return True, f"数值匹配: {std_num} == {act_num}"
                else:
                    return False, f"数值不匹配: {std_num} != {act_num}"
            except ValueError:
                return False, "数值解析失败"

        # 类型3：文本型答案
        if standard_value == actual_value:
            return True, f"文本完全匹配: {standard_value}"
        else:
            return False, f"文本不匹配: '{standard_value}' != '{actual_value}'"

    def _compare_multi_entity_answer(self, standard_answer: str, actual_answer: str) -> tuple[bool, str]:
        """比较多实体对比答案（如"一汽大众: 9533 辆, 比亚迪: 31140 辆"）"""
        # 解析标准答案
        std_entities = self._parse_multi_entity(standard_answer)
        # 解析实际答案
        act_entities = self._parse_multi_entity(actual_answer)
        
        # 检查每个实体
        all_match = True
        mismatch_details = []
        
        for entity_name, value in std_entities.items():
            if entity_name in act_entities:
                if value == act_entities[entity_name]:
                    pass  # 匹配
                else:
                    all_match = False
                    mismatch_details.append(f"{entity_name}: {value} != {act_entities[entity_name]}")
            else:
                all_match = False
                mismatch_details.append(f"{entity_name} 缺失")
        
        if all_match:
            return True, "多实体完全匹配"
        else:
            return False, f"多实体不匹配: {', '.join(mismatch_details)}"

    def _compare_time_series_answer(self, standard_answer: str, actual_answer: str) -> tuple[bool, str]:
        """比较时间序列答案（如"1月: 4890辆; 2月: 3217辆; ..."）"""
        # 解析标准答案
        std_series = self._parse_time_series(standard_answer)
        # 解析实际答案
        act_series = self._parse_time_series(actual_answer)
        
        # 检查每个月份是否匹配
        all_match = True
        mismatch_count = 0
        
        for month, value in std_series.items():
            if month in act_series:
                if value == act_series[month]:
                    pass  # 匹配
                else:
                    # 尝试数值比较（忽略格式差异）
                    std_num = self._extract_numeric_value(value)
                    act_num = self._extract_numeric_value(act_series[month])
                    if std_num == act_num:
                        pass  # 数值匹配
                    else:
                        all_match = False
                        mismatch_count += 1
            else:
                all_match = False
                mismatch_count += 1
        
        if all_match:
            return True, "时间序列完全匹配"
        elif mismatch_count == 1:
            # 只有一个不匹配，检查是否是单位差异（如"辆"的有无）
            return True, "时间序列匹配（忽略微小格式差异）"
        else:
            return False, f"时间序列不匹配: {mismatch_count}个月份不匹配"

    def _parse_multi_entity(self, text: str) -> dict:
        """解析多实体答案（如"一汽大众: 9533 辆, 比亚迪: 31140 辆"）"""
        entities = {}
        # 按逗号或分号分割
        parts = re.split(r'[,;]', text)
        for part in parts:
            # 每个部分的格式：实体名: 数值
            match = re.search(r'([^:：,]+)[:][:,：,](.+)', part)
            if match:
                entity_name = match.group(1).strip()
                value = match.group(2).strip()
                entities[entity_name] = value
        return entities

    def _parse_time_series(self, text: str) -> dict:
        """解析时间序列答案（如"1月: 4890辆; 2月: 3217辆"）"""
        series = {}
        # 按分号分割
        parts = text.split(';')
        for part in parts:
            # 每个部分的格式：月份: 数值
            match = re.search(r'(\d+月)[:[:](.+)', part)
            if match:
                month = match.group(1).strip()
                value = match.group(2).strip()
                series[month] = value
        return series

    def _is_time_series(self, text: str) -> bool:
        """判断是否为时间序列答案"""
        return '月:' in text and ';' in text

    def _extract_value(self, text: str) -> str:
        """从文本中提取关键值"""
        if not text:
            return ""
        numbers = re.findall(r'-?\d+\.?\d*%?', text)
        if numbers:
            return numbers[0]
        return text.strip()

    def _extract_numeric_value(self, text: str) -> str:
        """提取数值（忽略单位）"""
        if not text:
            return ""
        # 提取数值
        match = re.search(r'-?\d+\.?\d*', text)
        if match:
            return match.group(0)
        return ""

    def _is_numeric(self, text: str) -> bool:
        """判断文本是否为数值型"""
        try:
            cleaned = text.rstrip('%')
            float(cleaned)
            return True
        except ValueError:
            return False


def generate_fingerprint(question: str) -> str:
    """生成问题指纹"""
    if not question:
        return ""
    import string
    translator = str.maketrans('', '', string.punctuation + string.whitespace + '，。！？；：')
    fingerprint = question.translate(translator)
    return fingerprint.lower()


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
    """加载问题和标准答案"""
    with open(questions_file, 'r', encoding='utf-8') as f:
        questions = f.readlines()

    with open(answers_file, 'r', encoding='utf-8') as f:
        answers = f.readlines()

    qa_pairs = []
    current_question = None
    current_answer = None
    
    for line in answers:
        line = line.strip()
        if not line:
            continue
        
        if re.match(r'^\d+\.\s*问题：', line):
            if current_question and current_answer:
                qa_pairs.append((current_question, current_answer))
            current_question = re.sub(r'^\d+\.\s*', '', line).replace('问题：', '')
            current_answer = None
        elif line.startswith('问题：'):
            if current_question and current_answer:
                qa_pairs.append((current_question, current_answer))
            current_question = line.replace('问题：', '')
            current_answer = None
        elif line.startswith('答案：'):
            current_answer = line.replace('答案：', '')

    if current_question and current_answer:
        qa_pairs.append((current_question, current_answer))

    return qa_pairs


class NL2SQLClient:
    """NL2SQL 客户端 - 简化版，用于批量测试"""

    def __init__(self):
        os.chdir(str(project_root))
        self.config = DatabaseConfig(workspace_root=project_root)
        self.db_manager = DatabaseConnectionManager(self.config)
        print(f"[OK] NL2SQL Client 初始化完成")

    async def query(self, question: str, query_index: int = None, timeout: int = 60) -> str:
        """查询 NL2SQL Agent，带超时保护"""
        from dbrheo.core.client import DatabaseClient
        from dbrheo.types.core_types import SimpleAbortSignal

        client = DatabaseClient(config=self.config)
        signal = SimpleAbortSignal()
        
        if query_index is not None:
            session_id = f"nl2sql_test_{query_index}_{datetime.now().strftime('%H%M%S_%f')}"
        else:
            session_id = f"query_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        response_parts = []

        try:
            response_stream = client.send_message_stream(
                request=question,
                signal=signal,
                prompt_id=session_id,
                turns=10
            )

            async def collect_response():
                async for chunk in response_stream:
                    if chunk.get("type") == "Content":
                        content = chunk.get("value", "")
                        if content:
                            response_parts.append(content)
                return "".join(response_parts)

            return await asyncio.wait_for(collect_response(), timeout=timeout)
        except asyncio.TimeoutError:
            return f"[TIMEOUT] 查询超时({timeout}秒)"
        except Exception as e:
            return f"[ERROR] 查询出错: {str(e)}"


async def run_nl2sql_batch_test(
    questions_file: str,
    answers_file: str,
    output_file: str,
    skip_existing: bool = True,
    question_indices: list[int] = None
):
    """批量测试 NL2SQL Agent"""
    print("=" * 80)
    print("批量测试 NL2SQL Agent")
    print("=" * 80)
    print(f"问题文件: {questions_file}")
    print(f"答案文件: {answers_file}")
    print(f"输出文件: {output_file}")
    print(f"跳过已存在: {skip_existing}")
    if question_indices:
        print(f"测试序号: {question_indices}")
    print("=" * 80)

    print("\n[1/4] 初始化 NL2SQL Client...")
    client = NL2SQLClient()
    comparator = AnswerComparator()

    print("\n[2/4] 加载问题和标准答案...")
    qa_pairs = load_questions_and_answers(questions_file, answers_file)
    total_questions = len(qa_pairs)
    print(f"加载了 {total_questions} 个问题")
    
    if question_indices:
        valid_indices = [i for i in question_indices if 1 <= i <= total_questions]
        if len(valid_indices) != len(question_indices):
            invalid = set(question_indices) - set(valid_indices)
            print(f"警告：以下序号超出范围（1-{total_questions}），已跳过: {invalid}")
        
        filtered_qa_pairs = []
        for i in valid_indices:
            filtered_qa_pairs.append(qa_pairs[i - 1])
        qa_pairs = filtered_qa_pairs
        print(f"筛选后测试 {len(qa_pairs)} 个问题（序号: {valid_indices}）")

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

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
            
            print(f"  [Session] {datetime.now().strftime('%H:%M:%S')} - 独立会话")
            try:
                response = await client.query(question, query_index=idx, timeout=60)
                actual_answer = extract_answer(response)

                # 检查是否超时
                if response.startswith("[TIMEOUT]"):
                    if attempt < max_retries:
                        print(f"  [TIMEOUT] 超时，将重试...")
                        continue
                    else:
                        print(f"  [TIMEOUT] 超时，已达最大重试次数")

                is_correct, reason = comparator.compare_answers(standard_answer, actual_answer)

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
                    'agent_type': 'NL2SQL',
                    'full_response': response
                }

                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(evaluation, ensure_ascii=False) + '\n')

                if is_correct:
                    success_count += 1
                    print(f"  [OK] 正确 | {reason}")
                else:
                    fail_count += 1
                    print(f"  [FAIL] 错误 | {reason}")
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
    questions_file = str(project_root / 'test' / 'question' / 'automotive_questions_list_100.csv')
    answers_file = str(project_root / 'test' / 'answer' / 'automotive_answers_100.csv')

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = str(Path(__file__).parent / f'evaluations_{timestamp}.jsonl')

    # 运行批量测试 - 测试所有100个问题
    asyncio.run(run_nl2sql_batch_test(
        questions_file=questions_file,
        answers_file=answers_file,
        output_file=output_file,
        skip_existing=False,
        question_indices=list(range(1, 101))  # 测试所有100个问题
    ))
