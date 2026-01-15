"""
DbRheo Gradio Web Interface
轻量级 Web 界面，提供数据库查询和 AI 对话功能
"""

import gradio as gr
import pandas as pd
from pathlib import Path
import sys
import os
import json
from datetime import datetime
import time
import re

# ===== 加载环境变量（在导入其他模块之前） =====
def load_env_file():
    """加载.env文件中的环境变量"""
    env_paths = [
        Path.cwd() / '.env',  # 当前工作目录
        Path(__file__).parent / '.env',  # gradio_app.py 同级目录
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            print(f"[OK] Load env: {env_path}")
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # 只设置未设置的环境变量
                        if key not in os.environ:
                            os.environ[key] = value
            return True
    
    print("[WARN] .env file not found")
    return False

# 在导入其他模块前加载环境变量
load_env_file()

# ===== 设置默认数据库路径 =====
# 将默认数据库设置为 vehicle_sales.db
if 'DATABASE_URL' not in os.environ and 'DBRHEO_DATABASE_URL' not in os.environ:
    db_path = Path(__file__).parent / "db" / "vehicle_sales.db"
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
    print(f"[OK] Set default database: {db_path}")

# ===== 添加核心包到路径 =====
sys.path.insert(0, str(Path(__file__).parent / "packages" / "core" / "src"))

from dbrheo.config.test_config import TestDatabaseConfig
from dbrheo.core.client import DatabaseClient

# 导入 Baseline Agent
sys.path.insert(0, str(Path(__file__).parent / "baseline"))


class LogCollector:
    """日志收集器，用于捕获交互流程信息"""
    def __init__(self):
        self.logs = []
        self.max_logs = 500  # 最多保留500条日志

    def add(self, component: str, message: str):
        """添加日志（格式与CLI一致）"""
        # 使用CLI的格式: [INFO Component]: message
        log_entry = f"[INFO {component}]: {message}"
        self.logs.append(log_entry)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

    def get_formatted_logs(self) -> str:
        """获取格式化的日志"""
        return "\n".join(self.logs)

    def clear(self):
        """清空日志"""
        self.logs = []
        return ""


class EvaluationManager:
    """评估管理器，用于记录和评估Agent查询结果"""
    def __init__(self):
        self.evaluations = []  # 评估记录列表
        self.evaluation_dir = Path(__file__).parent / "test" / "result"
        self.evaluation_dir.mkdir(parents=True, exist_ok=True)
        # 使用固定文件名，不再每次重启创建新文件
        self.current_evaluation_file = self.evaluation_dir / "evaluations.jsonl"
        # 启动时加载已有的评估数据
        self._load_existing_evaluations()

    def extract_answer(self, response_text: str) -> str:
        """从AI响应中提取答案 - 优化版
        
        支持多种格式：
        - 【答案：xxx】
        - 【答案:xxx】
        - 答案：xxx
        """
        if not response_text:
            return ""

        # 先移除所有空格（流式输出会在字符间插入空格）
        cleaned_text = response_text.replace(' ', '').replace('\n', '')

        # 尝试多种提取模式（在清理后的文本中匹配）
        patterns = [
            r'【答案[：:](.*?)】',  # 【答案：xxx】
            r'答案[：:](.*?)(?:$|[，。！？；])',  # 答案：xxx
        ]

        for pattern in patterns:
            match = re.search(pattern, cleaned_text)
            if match:
                answer = match.group(1).strip()
                return answer

        # 如果没有匹配到，尝试在原文中查找（保留空格）
        patterns_original = [
            r'【答案[：:]\s*([^】]+)】',
            r'答案[：:]\s*([^\n，。！？；]+)',
        ]
        
        for pattern in patterns_original:
            match = re.search(pattern, response_text)
            if match:
                answer = match.group(1).strip()
                return answer

        return ""

    def compare_answers(self, standard_answer: str, actual_answer: str) -> tuple[bool, str]:
        """比较标准答案和实际答案是否正确
        
        Returns:
            (is_correct, reason): 是否正确和原因说明
        """
        if not standard_answer or not actual_answer:
            return False, "答案为空"

        # 提取标准答案中的关键值
        standard_value = self._extract_value(standard_answer)
        actual_value = self._extract_value(actual_answer)

        # 类型1：百分比答案（如 -11.56%）
        if '%' in standard_answer and '%' in actual_answer:
            try:
                std_num = float(standard_value.rstrip('%'))
                act_num = float(actual_value.rstrip('%'))
                # 允许±5%的误差
                if abs(std_num - act_num) <= 5.0:
                    return True, f"百分比匹配: {std_num}% ≈ {act_num}%"
                else:
                    return False, f"百分比不匹配: {std_num}% vs {act_num}%"
            except ValueError:
                return False, "百分比解析失败"

        # 类型2：数值型答案
        if self._is_numeric(standard_value) and self._is_numeric(actual_value):
            try:
                std_num = float(standard_value)
                act_num = float(actual_value)
                # 允许±5%的相对误差
                if std_num == 0:
                    tolerance = 0
                else:
                    tolerance = abs(std_num) * 0.05

                if abs(std_num - act_num) <= tolerance:
                    return True, f"数值匹配: {std_num} ≈ {act_num}"
                else:
                    return False, f"数值不匹配: {std_num} vs {act_num}"
            except ValueError:
                return False, "数值解析失败"

        # 类型3：文本型答案 - 包含关系
        if standard_value in actual_answer or actual_value in standard_answer:
            return True, f"文本匹配: 包含关系"

        # 类型4：完全匹配
        if standard_value == actual_value:
            return True, f"完全匹配: {standard_value}"

        # 其他情况 - 不匹配
        return False, f"答案不匹配: '{standard_value}' vs '{actual_value}'"

    def _extract_value(self, text: str) -> str:
        """从文本中提取关键值"""
        if not text:
            return ""

        # 提取数字（可能带百分比）
        numbers = re.findall(r'-?\d+\.?\d*%?', text)
        if numbers:
            return numbers[0]

        # 如果没有数字，返回清理后的文本
        return ' '.join(text.split())

    def _is_numeric(self, text: str) -> bool:
        """判断文本是否为数值型"""
        try:
            # 去掉百分比符号
            cleaned = text.rstrip('%')
            float(cleaned)
            return True
        except ValueError:
            return False

    def add_evaluation(self, question: str, standard_answer: str, actual_response: str,
                      agent_type: str = "NL2SQL"):
        """添加评估记录

        Args:
            question: 问题文本
            standard_answer: 标准答案
            actual_response: AI实际响应（完整文本）
            agent_type: Agent类型 (NL2SQL 或 Baseline)
        """
        actual_answer = self.extract_answer(actual_response)
        is_correct, reason = self.compare_answers(standard_answer, actual_answer)

        # 生成问题指纹（用于识别同一问题）
        question_fingerprint = self._generate_fingerprint(question)

        # 计算运行次数
        run_number = self._get_run_number(question_fingerprint, agent_type)

        evaluation = {
            'id': len(self.evaluations) + 1,
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'question_fingerprint': question_fingerprint,  # 问题指纹
            'run_number': run_number,  # 运行次数
            'standard_answer': standard_answer,
            'actual_answer': actual_answer,
            'is_correct': is_correct,
            'comparison_reason': reason,
            'agent_type': agent_type,
            'full_response': actual_response
        }

        self.evaluations.append(evaluation)
        print(f"[EVALUATION] 记录 #{evaluation['id']} [{agent_type}] 第{run_number}次: {question[:50]}... -> {'✓ 正确' if is_correct else '✗ 错误'}")

        # 持久化保存
        self._save_evaluation(evaluation)

        return evaluation

    def _generate_fingerprint(self, question: str) -> str:
        """生成问题指纹（用于识别同一问题）

        去除空格、标点，统一大小写
        """
        if not question:
            return ""

        # 去除所有空格、标点、特殊字符
        import string
        translator = str.maketrans('', '', string.punctuation + string.whitespace + '，。！？；：')
        fingerprint = question.translate(translator)

        # 统一为小写
        fingerprint = fingerprint.lower()

        return fingerprint

    def _get_run_number(self, question_fingerprint: str, agent_type: str) -> int:
        """获取该问题在该Agent中的运行次数"""
        count = 0
        for eval in self.evaluations:
            if (eval.get('question_fingerprint') == question_fingerprint and
                eval.get('agent_type') == agent_type):
                count += 1
        return count + 1

    def _load_existing_evaluations(self):
        """启动时加载已有的评估数据"""
        if not self.current_evaluation_file.exists():
            print(f"[EVALUATION] 无已有评估数据")
            return
        
        try:
            with open(self.current_evaluation_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        evaluation = json.loads(line)
                        self.evaluations.append(evaluation)
            print(f"[EVALUATION] 已加载 {len(self.evaluations)} 条评估记录")
        except Exception as e:
            print(f"[EVALUATION] 加载失败: {e}")

    def _save_evaluation(self, evaluation: dict):
        """保存评估记录到文件（追加到固定文件）"""
        try:
            with open(self.current_evaluation_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(evaluation, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[EVALUATION] 保存失败: {e}")

    def get_evaluation_dataframe(self, agent_filter: str = "全部", question_keyword: str = None) -> pd.DataFrame:
        """获取评估结果的DataFrame

        Args:
            agent_filter: Agent类型筛选 ("全部", "NL2SQL", "Baseline")
            question_keyword: 问题关键词（用于搜索）

        Returns:
            评估结果的DataFrame
        """
        if not self.evaluations:
            return pd.DataFrame(columns=[
                'ID', '时间', '运行次数', '问题', '标准答案', '实际答案',
                '是否正确', '比较原因', 'Agent类型'
            ])

        # 过滤评估记录
        filtered = self.evaluations

        if agent_filter != "全部":
            filtered = [e for e in filtered if e['agent_type'] == agent_filter]

        if question_keyword:
            keyword = question_keyword.lower()
            filtered = [e for e in filtered if keyword in e['question'].lower()]

        df = pd.DataFrame(filtered)
        df['time'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df['id'] = df['id']
        df['run_number'] = df.get('run_number', 1)
        df['is_correct_str'] = df['is_correct'].map({True: '✓ 正确', False: '✗ 错误'})

        return df[['id', 'time', 'run_number', 'question', 'standard_answer', 'actual_answer',
                   'is_correct_str', 'comparison_reason', 'agent_type']]

    def get_question_details(self, question_fingerprint: str, agent_type: str = None) -> pd.DataFrame:
        """获取某个问题的所有运行记录

        Args:
            question_fingerprint: 问题指纹
            agent_type: Agent类型筛选（可选）

        Returns:
            该问题的所有运行记录
        """
        filtered = [e for e in self.evaluations if e.get('question_fingerprint') == question_fingerprint]

        if agent_type:
            filtered = [e for e in filtered if e['agent_type'] == agent_type]

        df = pd.DataFrame(filtered)
        if len(df) == 0:
            return pd.DataFrame(columns=['ID', '时间', 'Agent类型', '运行次数', '实际答案', '是否正确'])

        df['time'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df['id'] = df['id']
        df['run_number'] = df.get('run_number', 1)
        df['is_correct_str'] = df['is_correct'].map({True: '✓ 正确', False: '✗ 错误'})

        return df[['id', 'time', 'agent_type', 'run_number', 'actual_answer', 'is_correct_str']]

    def search_questions(self, keyword: str) -> list[dict]:
        """搜索问题（返回匹配的问题及其指纹）

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的问题列表 [{'fingerprint': '...', 'question': '...'}, ...]
        """
        if not keyword:
            return []

        keyword_lower = keyword.lower()
        seen = {}

        results = []
        for eval in self.evaluations:
            question = eval['question']
            fingerprint = eval.get('question_fingerprint', '')

            if keyword_lower in question.lower():
                # 去重（同一个问题只返回一次）
                if fingerprint not in seen:
                    seen[fingerprint] = True
                    results.append({
                        'fingerprint': fingerprint,
                        'question': question,
                        'count': sum(1 for e in self.evaluations if e.get('question_fingerprint') == fingerprint)
                    })

        return results

    def get_statistics(self) -> dict:
        """获取统计信息（所有记录）"""
        if not self.evaluations:
            return {
                'total': 0,
                'correct': 0,
                'accuracy': 0.0,
                'by_agent': {}
            }

        total = len(self.evaluations)
        correct = sum(1 for e in self.evaluations if e['is_correct'])
        accuracy = correct / total * 100 if total > 0 else 0.0

        # 按Agent类型统计
        by_agent = {}
        for agent in ['NL2SQL', 'Baseline']:
            agent_evals = [e for e in self.evaluations if e['agent_type'] == agent]
            if agent_evals:
                agent_correct = sum(1 for e in agent_evals if e['is_correct'])
                by_agent[agent] = {
                    'total': len(agent_evals),
                    'correct': agent_correct,
                    'accuracy': agent_correct / len(agent_evals) * 100
                }

        return {
            'total': total,
            'correct': correct,
            'accuracy': accuracy,
            'by_agent': by_agent
        }

    def get_statistics_by_agent_latest(self) -> dict:
        """按Agent类型统计（每个问题只取最新结果，最多100条）

        Returns:
            {
                'NL2SQL': {'total': 10, 'correct': 8, 'accuracy': 80.0},
                'Baseline': {'total': 10, 'correct': 6, 'accuracy': 60.0},
                'winner': 'NL2SQL'
            }
        """
        if not self.evaluations:
            return {
                'NL2SQL': {'total': 0, 'correct': 0, 'accuracy': 0.0},
                'Baseline': {'total': 0, 'correct': 0, 'accuracy': 0.0},
                'winner': None
            }

        # 按问题-Agent组合分组，取最新
        results = {'NL2SQL': {}, 'Baseline': {}}

        for eval in self.evaluations:
            fp = eval.get('question_fingerprint', '')
            agent = eval['agent_type']
            timestamp = eval['timestamp']

            # 如果该问题-Agent组合不存在，或当前记录更新
            if fp not in results[agent] or timestamp > results[agent][fp]['timestamp']:
                results[agent][fp] = eval

        # 计算每个Agent的正确率
        stats = {}
        for agent in ['NL2SQL', 'Baseline']:
            # 按时间倒序排列，取最新100条（从后往前）
            agent_evals = sorted(results[agent].values(), key=lambda x: x['timestamp'], reverse=True)
            agent_evals = agent_evals[:100]

            correct = sum(1 for e in agent_evals if e['is_correct'])
            total = len(agent_evals)
            stats[agent] = {
                'total': total,
                'correct': correct,
                'accuracy': correct / total * 100 if total > 0 else 0.0
            }

        # 判断胜者
        winner = None
        if stats['NL2SQL']['total'] > 0 and stats['Baseline']['total'] > 0:
            if stats['NL2SQL']['accuracy'] > stats['Baseline']['accuracy']:
                winner = 'NL2SQL'
            elif stats['Baseline']['accuracy'] > stats['NL2SQL']['accuracy']:
                winner = 'Baseline'
            else:
                winner = '平局'
        elif stats['NL2SQL']['total'] > 0:
            winner = 'NL2SQL'
        elif stats['Baseline']['total'] > 0:
            winner = 'Baseline'

        return {
            'NL2SQL': stats['NL2SQL'],
            'Baseline': stats['Baseline'],
            'winner': winner
        }

    def export_csv(self, export_path: str = None) -> str:
        """导出评估结果为CSV（每个问题只取最新记录）

        Returns:
            导出信息（包含统计）
        """
        if not self.evaluations:
            return "⚠️ 没有评估记录可导出"

        if not export_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = self.evaluation_dir / f"evaluation_export_{timestamp}.csv"

        # 按问题-Agent组合去重，只保留最新记录
        latest_records = {}
        for eval in self.evaluations:
            key = (eval.get('question_fingerprint', ''), eval['agent_type'])
            timestamp = eval['timestamp']
            if key not in latest_records or timestamp > latest_records[key]['timestamp']:
                latest_records[key] = eval
        
        # 转换为DataFrame
        filtered_evals = list(latest_records.values())
        if not filtered_evals:
            return "⚠️ 没有评估记录可导出"
            
        df = pd.DataFrame(filtered_evals)
        df['time'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df['is_correct_str'] = df['is_correct'].map({True: '✓ 正确', False: '✗ 错误'})
        df = df[['id', 'time', 'run_number', 'question', 'standard_answer', 'actual_answer',
                 'is_correct_str', 'comparison_reason', 'agent_type']]
        
        total = len(df)
        correct = len(df[df['is_correct_str'] == '✓ 正确'])
        failed = total - correct
        
        df.columns = ['ID', '时间', '运行次数', '问题', '标准答案', '实际答案', '是否正确', '比较原因', 'Agent类型']
        df.to_csv(export_path, index=False, encoding='utf-8-sig')

        print(f"[EVALUATION] 导出到: {export_path}")
        return f"✓ 导出成功（去重后）\n路径: {export_path}\n总记录: {total} | 成功: {correct} | 失败: {failed}"

    def export_excel(self, export_path: str = None) -> str:
        """导出评估结果为Excel（每个问题只取最新记录，多sheet格式）

        Sheet 1: NL2SQL 评估结果
        Sheet 2: Baseline 评估结果
        Sheet 3: 统计分析和失败原因分析

        Returns:
            导出信息（包含统计）
        """
        if not self.evaluations:
            return "⚠️ 没有评估记录可导出"

        if not export_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = self.evaluation_dir / f"evaluation_export_{timestamp}.xlsx"

        # 按问题-Agent组合去重，只保留最新记录
        latest_records = {}
        for eval in self.evaluations:
            key = (eval.get('question_fingerprint', ''), eval['agent_type'])
            timestamp = eval['timestamp']
            if key not in latest_records or timestamp > latest_records[key]['timestamp']:
                latest_records[key] = eval
        
        filtered_evals = list(latest_records.values())
        if not filtered_evals:
            return "⚠️ 没有评估记录可导出"
        
        # 准备数据
        df_all = pd.DataFrame(filtered_evals)
        df_all['time'] = pd.to_datetime(df_all['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df_all['is_correct_str'] = df_all['is_correct'].map({True: '✓ 正确', False: '✗ 错误'})
        df_all = df_all[['id', 'time', 'run_number', 'question', 'standard_answer', 'actual_answer',
                         'is_correct_str', 'comparison_reason', 'agent_type']]
        
        # 分别获取 NL2SQL 和 Baseline 的数据
        df_nl2sql = df_all[df_all['agent_type'] == 'NL2SQL'].copy()
        df_baseline = df_all[df_all['agent_type'] == 'Baseline'].copy()
        
        # 重命名列
        for df in [df_nl2sql, df_baseline]:
            df.columns = ['ID', '时间', '运行次数', '问题', '标准答案', '实际答案', '是否正确', '比较原因', 'Agent类型']
        
        # 准备统计分析和失败原因分析
        stats_nl2sql = self.analyze_nl2sql_failures()
        stats_baseline = self.analyze_baseline_failures()
        stats_comparison = self.get_statistics_by_agent_latest()
        
        # 创建统计汇总 DataFrame
        stats_data = {
            '指标': ['总问题数', '正确数', '失败数', '准确率 (%)'],
            'NL2SQL': [
                stats_nl2sql['total'],
                stats_nl2sql['correct'],
                stats_nl2sql['failed'],
                f"{stats_nl2sql['accuracy']:.2f}"
            ],
            'Baseline': [
                stats_baseline['total'],
                stats_baseline['correct'],
                stats_baseline['failed'],
                f"{stats_baseline['accuracy']:.2f}"
            ]
        }
        df_stats = pd.DataFrame(stats_data)
        
        # 创建失败原因分析 DataFrame
        failure_reasons_data = []
        
        # NL2SQL 失败原因
        for reason, count in stats_nl2sql['failure_reasons'].items():
            if count > 0:
                failure_reasons_data.append({
                    'Agent': 'NL2SQL',
                    '失败原因': reason,
                    '数量': count,
                    '占比': f"{count / stats_nl2sql['failed'] * 100:.1f}%" if stats_nl2sql['failed'] > 0 else "0%"
                })
        
        # Baseline 失败原因
        for reason, count in stats_baseline['failure_reasons'].items():
            if count > 0:
                failure_reasons_data.append({
                    'Agent': 'Baseline',
                    '失败原因': reason,
                    '数量': count,
                    '占比': f"{count / stats_baseline['failed'] * 100:.1f}%" if stats_baseline['failed'] > 0 else "0%"
                })
        
        df_failures = pd.DataFrame(failure_reasons_data)
        
        # 创建对比分析 DataFrame
        comparison_data = {
            '对比项目': [
                'NL2SQL 准确率',
                'Baseline 准确率',
                '准确率差异',
                'NL2SQL 总问题数',
                'Baseline 总问题数',
                '胜出方案'
            ],
            '值': [
                f"{stats_comparison['NL2SQL']['accuracy']:.2f}%",
                f"{stats_comparison['Baseline']['accuracy']:.2f}%",
                f"{stats_comparison['NL2SQL']['accuracy'] - stats_comparison['Baseline']['accuracy']:+.2f}%",
                stats_comparison['NL2SQL']['total'],
                stats_comparison['Baseline']['total'],
                stats_comparison['winner'] or '无足够数据'
            ]
        }
        df_comparison = pd.DataFrame(comparison_data)
        
        # 导出到多个 sheet
        try:
            with pd.ExcelWriter(export_path, engine='openpyxl') as writer:
                # Sheet 1: NL2SQL 评估结果
                if len(df_nl2sql) > 0:
                    df_nl2sql.to_excel(writer, sheet_name='NL2SQL评估结果', index=False)
                else:
                    pd.DataFrame({'提示': ['暂无 NL2SQL 评估数据']}).to_excel(writer, sheet_name='NL2SQL评估结果', index=False)
                
                # Sheet 2: Baseline 评估结果
                if len(df_baseline) > 0:
                    df_baseline.to_excel(writer, sheet_name='Baseline评估结果', index=False)
                else:
                    pd.DataFrame({'提示': ['暂无 Baseline 评估数据']}).to_excel(writer, sheet_name='Baseline评估结果', index=False)
                
                # Sheet 3: 统计分析
                df_stats.to_excel(writer, sheet_name='统计分析', index=False)
                
                # Sheet 4: 失败原因分析
                if len(df_failures) > 0:
                    df_failures.to_excel(writer, sheet_name='失败原因分析', index=False)
                else:
                    pd.DataFrame({'提示': ['暂无失败数据']}).to_excel(writer, sheet_name='失败原因分析', index=False)
                
                # Sheet 5: 对比分析
                df_comparison.to_excel(writer, sheet_name='对比分析', index=False)
            
            # 统计总记录数
            total_nl2sql = len(df_nl2sql)
            total_baseline = len(df_baseline)
            total_all = total_nl2sql + total_baseline
            
            print(f"[EVALUATION] 导出到: {export_path}")
            return (f"✓ 导出成功（多Sheet Excel）\n"
                   f"路径: {export_path}\n"
                   f"NL2SQL 记录: {total_nl2sql} | Baseline 记录: {total_baseline} | 总计: {total_all}\n"
                   f"包含5个Sheet: NL2SQL评估结果、Baseline评估结果、统计分析、失败原因分析、对比分析")
        except ImportError:
            print(f"[EVALUATION] openpyxl未安装，改用CSV格式")
            csv_path = str(export_path).replace('.xlsx', '.csv')
            df_all.to_csv(csv_path, index=False, encoding='utf-8-sig')
            return f"✓ 导出成功（CSV格式）\n路径: {csv_path}\n总记录: {len(df_all)}"
        except Exception as e:
            print(f"[EVALUATION] 导出失败: {e}")
            return f"✗ 导出失败: {e}"

    def update_evaluation(self, evaluation_id: int, **kwargs):
        """更新评估记录
        
        Args:
            evaluation_id: 评估记录ID
            **kwargs: 要更新的字段（standard_answer, actual_answer, is_correct等）
            
        Returns:
            (success, message): 是否成功和消息
        """
        # 查找评估记录
        eval_record = None
        for eval in self.evaluations:
            if eval['id'] == evaluation_id:
                eval_record = eval
                break
        
        if not eval_record:
            return False, f"未找到ID为{evaluation_id}的评估记录"
        
        # 更新字段
        updated_fields = []
        for key, value in kwargs.items():
            if key in ['standard_answer', 'actual_answer', 'is_correct', 'comparison_reason']:
                old_value = eval_record.get(key)
                eval_record[key] = value
                updated_fields.append(f"{key}: {old_value} -> {value}")
        
        # 如果更新了标准答案或实际答案，重新比较
        if 'standard_answer' in kwargs or 'actual_answer' in kwargs:
            actual_answer = self.extract_answer(eval_record.get('full_response', ''))
            is_correct, reason = self.compare_answers(eval_record['standard_answer'], actual_answer)
            eval_record['is_correct'] = is_correct
            eval_record['comparison_reason'] = reason
            updated_fields.append(f"is_correct: -> {is_correct}")
            updated_fields.append(f"comparison_reason: -> {reason}")
        
        print(f"[EVALUATION] 更新记录 #{evaluation_id}: {', '.join(updated_fields)}")
        
        # 重新保存到文件（覆盖原文件）
        self._rewrite_evaluation_file()
        
        return True, f"✓ 已更新记录 #{evaluation_id}"

    def delete_evaluation(self, evaluation_id: int):
        """删除单条评估记录
        
        Args:
            evaluation_id: 评估记录ID
            
        Returns:
            (success, message): 是否成功和消息
        """
        # 查找并删除评估记录
        deleted_record = None
        self.evaluations = [e for e in self.evaluations if e['id'] != evaluation_id]
        
        # 检查是否删除成功
        if len(self.evaluations) == deleted_record:
            return False, f"未找到ID为{evaluation_id}的评估记录"
        
        print(f"[EVALUATION] 删除记录 #{evaluation_id}")
        
        # 重新保存到文件
        self._rewrite_evaluation_file()
        
        return True, f"✓ 已删除记录 #{evaluation_id}"

    def delete_evaluations(self, evaluation_ids: list):
        """批量删除评估记录
        
        Args:
            evaluation_ids: 评估记录ID列表
            
        Returns:
            (success, message, count): 是否成功、消息、删除数量
        """
        original_count = len(self.evaluations)
        self.evaluations = [e for e in self.evaluations if e['id'] not in evaluation_ids]
        deleted_count = original_count - len(self.evaluations)
        
        if deleted_count == 0:
            return False, "未找到可删除的记录", 0
        
        print(f"[EVALUATION] 批量删除 {deleted_count} 条记录")
        
        # 重新保存到文件
        self._rewrite_evaluation_file()
        
        return True, f"✓ 已删除 {deleted_count} 条记录", deleted_count

    def _rewrite_evaluation_file(self):
        """重写评估文件（删除或更新后调用）"""
        try:
            # 备份原文件
            if self.current_evaluation_file.exists():
                backup_path = self.current_evaluation_file.with_suffix('.jsonl.bak')
                import shutil
                shutil.copy2(self.current_evaluation_file, backup_path)
            
            # 重写文件
            with open(self.current_evaluation_file, 'w', encoding='utf-8') as f:
                for eval in self.evaluations:
                    f.write(json.dumps(eval, ensure_ascii=False) + '\n')
            
            print(f"[EVALUATION] 已重写文件: {self.current_evaluation_file}")
        except Exception as e:
            print(f"[EVALUATION] 重写文件失败: {e}")

    def clear(self):
        """清空评估记录（仅清空内存，不删除文件）"""
        self.evaluations = []
        print(f"[EVALUATION] 已清空内存中的评估记录")

    def analyze_baseline_failures(self):
        """分析 Baseline 的失败原因（按时间从后往前，每个问题只取最新，最多100条）

        Returns:
            dict: {
                'total': 总问题数,
                'correct': 正确数,
                'failed': 失败数,
                'failure_reasons': {
                    '数值计算错误': count,
                    '数据筛选错误': count,
                    '其他错误': count
                },
                'failed_questions': [失败问题列表]
            }
        """
        # 获取 Baseline 的最新记录（每个问题只取最新）
        baseline_latest = {}
        for eval in self.evaluations:
            if eval['agent_type'] == 'Baseline':
                fp = eval.get('question_fingerprint', '')
                timestamp = eval['timestamp']
                if fp not in baseline_latest or timestamp > baseline_latest[fp]['timestamp']:
                    baseline_latest[fp] = eval

        # 转换为列表并按时间倒序排列（从后往前）
        latest_evals = sorted(baseline_latest.values(), key=lambda x: x['timestamp'], reverse=True)

        # 限制为100条记录（从后往前取）
        latest_evals = latest_evals[:100]

        # 统计
        total = len(latest_evals)
        correct = sum(1 for e in latest_evals if e['is_correct'])
        failed = total - correct

        # 分析失败原因
        failure_reasons = {
            '数值计算错误': 0,
            '数据筛选错误': 0,
            '其他错误': 0
        }

        failed_questions = []

        for eval in latest_evals:
            if not eval['is_correct']:
                reason = eval.get('comparison_reason', '')
                question = eval['question']
                standard = eval['standard_answer']
                actual = eval['actual_answer']

                # 分类失败原因
                category = self._categorize_failure(reason, standard, actual)
                failure_reasons[category] += 1

                failed_questions.append({
                    'question': question,
                    'standard_answer': standard,
                    'actual_answer': actual,
                    'reason': reason,
                    'category': category
                })

        return {
            'total': total,
            'correct': correct,
            'failed': failed,
            'accuracy': correct / total * 100 if total > 0 else 0,
            'failure_reasons': failure_reasons,
            'failed_questions': failed_questions
        }
    
    def _categorize_failure(self, reason: str, standard: str, actual: str) -> str:
        """分类失败原因
        
        Args:
            reason: 比较原因
            standard: 标准答案
            actual: 实际答案
            
        Returns:
            '数值计算错误' | '数据筛选错误' | '其他错误'
        """
        # 提取数值
        std_nums = re.findall(r'-?\d+\.?\d*', standard)
        act_nums = re.findall(r'-?\d+\.?\d*', actual)
        
        # 如果都有数值，判断是计算错误还是筛选错误
        if std_nums and act_nums:
            try:
                std_val = float(std_nums[0])
                act_val = float(act_nums[0])
                
                # 如果差异很大（>20%），可能是数据筛选错误
                if std_val != 0:
                    diff_ratio = abs(std_val - act_val) / abs(std_val)
                    if diff_ratio > 0.2:
                        return '数据筛选错误'
                    else:
                        return '数值计算错误'
                else:
                    return '数值计算错误'
            except:
                pass
        
        # 如果标准答案有数值但实际答案没有，可能是筛选错误
        if std_nums and not act_nums:
            return '数据筛选错误'
        
        # 其他情况
        return '其他错误'
    
    def generate_failure_chart(self):
        """生成失败原因图表（饼图）

        Returns:
            plotly figure object
        """
        try:
            import plotly.graph_objects as go

            # 每次都重新分析数据（确保实时加载）
            analysis = self.analyze_baseline_failures()
            failure_reasons = analysis['failure_reasons']

            # 打印调试信息
            print(f"[EVALUATION] 生成失败原因图表: 总数={analysis['total']}, 失败={analysis['failed']}, 成功={analysis['correct']}")
            print(f"[EVALUATION] 失败原因: {failure_reasons}")

            # 过滤掉计数为0的类别
            labels = [k for k, v in failure_reasons.items() if v > 0]
            values = [v for v in failure_reasons.values() if v > 0]

            if not labels:
                # 如果没有失败，显示全部正确
                labels = ['全部正确']
                values = [analysis['correct']]

            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=0.3,
                marker=dict(colors=['#10b981', '#ef4444', '#f59e0b', '#6b7280'])
            )])

            fig.update_layout(
                title=f"Baseline 失败原因分析（共 {analysis['total']} 条，失败 {analysis['failed']} 个）",
                showlegend=True,
                height=400
            )

            return fig
        except ImportError:
            print("[EVALUATION] Plotly 未安装，无法生成图表")
            return None
        except Exception as e:
            print(f"[EVALUATION] 生成失败原因图表时出错: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def generate_comparison_chart(self):
        """生成 NL2SQL vs Baseline 对比柱状图（最多100条）

        Returns:
            plotly figure object
        """
        try:
            import plotly.graph_objects as go

            # 每次都重新分析数据（确保实时加载）
            stats = self.get_statistics_by_agent_latest()

            # 打印调试信息
            print(f"[EVALUATION] 生成对比图表: NL2SQL={stats['NL2SQL']}, Baseline={stats['Baseline']}")

            agents = ['NL2SQL', 'Baseline']
            correct = [stats[agent]['correct'] for agent in agents]
            total = [stats[agent]['total'] for agent in agents]
            failed = [total[i] - correct[i] for i in range(len(agents))]

            fig = go.Figure(data=[
                go.Bar(name='正确', x=agents, y=correct, marker_color='#10b981'),
                go.Bar(name='失败', x=agents, y=failed, marker_color='#ef4444')
            ])

            fig.update_layout(
                title=f'NL2SQL vs Baseline 对比（最近100条）',
                barmode='stack',
                yaxis_title='问题数量',
                height=400,
                showlegend=True
            )

            return fig
        except ImportError:
            print("[EVALUATION] Plotly 未安装，无法生成图表")
            return None
        except Exception as e:
            print(f"[EVALUATION] 生成对比图表时出错: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def analyze_nl2sql_failures(self):
        """分析 NL2SQL 的失败原因（每个问题只取最新，最多100条）
        
        Returns:
            {
                'total': 总数,
                'correct': 正确数,
                'failed': 失败数,
                'accuracy': 准确率,
                'failure_reasons': {'原因1': 数量, ...},
                'failed_questions': [...]
            }
        """
        if not self.evaluations:
            return {
                'total': 0,
                'correct': 0,
                'failed': 0,
                'accuracy': 0,
                'failure_reasons': {},
                'failed_questions': []
            }
        
        # 找出 NL2SQL 的最新评估结果
        nl2sql_latest = {}
        for eval in self.evaluations:
            if eval.get('agent_type') == 'NL2SQL':
                fp = eval.get('question_fingerprint', '')
                timestamp = eval['timestamp']
                if fp not in nl2sql_latest or timestamp > nl2sql_latest[fp]['timestamp']:
                    nl2sql_latest[fp] = eval
        
        # 按时间倒序排列，取最新100条
        latest_evals = sorted(nl2sql_latest.values(), key=lambda x: x['timestamp'], reverse=True)
        latest_evals = latest_evals[:100]
        
        total = len(latest_evals)
        correct = sum(1 for e in latest_evals if e['is_correct'])
        failed = total - correct
        
        # 统计失败原因
        failure_reasons = {
            '数值计算错误': 0,
            '数据筛选错误': 0,
            '答案为空': 0,
            '其他错误': 0
        }
        
        failed_questions = []
        for eval in latest_evals:
            if not eval['is_correct']:
                question = eval['question']
                standard = eval['standard_answer']
                actual = eval['actual_answer']
                reason = eval.get('comparison_reason', '')
                
                # 分类失败原因
                category = self._categorize_nl2sql_failure(reason, standard, actual)
                failure_reasons[category] += 1
                
                failed_questions.append({
                    'question': question,
                    'standard_answer': standard,
                    'actual_answer': actual,
                    'reason': reason,
                    'category': category
                })
        
        return {
            'total': total,
            'correct': correct,
            'failed': failed,
            'accuracy': correct / total * 100 if total > 0 else 0,
            'failure_reasons': failure_reasons,
            'failed_questions': failed_questions
        }
    
    def _categorize_nl2sql_failure(self, reason: str, standard: str, actual: str) -> str:
        """分类 NL2SQL 失败原因
        
        Args:
            reason: 比较原因
            standard: 标准答案
            actual: 实际答案
            
        Returns:
            '数值计算错误' | '数据筛选错误' | '答案为空' | '其他错误'
        """
        # 如果实际答案为空
        if not actual or actual.lower() == 'null':
            return '答案为空'
        
        # 提取数值
        std_nums = re.findall(r'-?\d+\.?\d*', standard)
        act_nums = re.findall(r'-?\d+\.?\d*', actual)
        
        # 如果都有数值，判断是计算错误还是筛选错误
        if std_nums and act_nums:
            try:
                std_val = float(std_nums[0])
                act_val = float(act_nums[0])
                
                # 如果差异很大（>20%），可能是数据筛选错误
                if std_val != 0:
                    diff_ratio = abs(std_val - act_val) / abs(std_val)
                    if diff_ratio > 0.2:
                        return '数据筛选错误'
                    else:
                        return '数值计算错误'
                else:
                    return '数值计算错误'
            except:
                pass
        
        # 如果标准答案有数值但实际答案没有，可能是筛选错误
        if std_nums and not act_nums:
            return '数据筛选错误'
        
        # 其他情况
        return '其他错误'
    
    def generate_nl2sql_failure_chart(self):
        """生成 NL2SQL 失败原因图表（饼图）
        
        Returns:
            plotly figure object
        """
        try:
            import plotly.graph_objects as go
            
            # 每次都重新分析数据（确保实时加载）
            analysis = self.analyze_nl2sql_failures()
            failure_reasons = analysis['failure_reasons']
            
            # 打印调试信息
            print(f"[EVALUATION] 生成 NL2SQL 失败原因图表: 总数={analysis['total']}, 失败={analysis['failed']}, 成功={analysis['correct']}")
            print(f"[EVALUATION] 失败原因: {failure_reasons}")
            
            # 过滤掉计数为0的类别
            labels = [k for k, v in failure_reasons.items() if v > 0]
            values = [v for v in failure_reasons.values() if v > 0]
            
            if not labels:
                # 如果没有失败，显示全部正确
                labels = ['全部正确']
                values = [analysis['correct']]
            
            fig = go.Figure(data=[go.Pie(
                labels=labels,
                values=values,
                hole=0.3,
                marker=dict(colors=['#10b981', '#ef4444', '#f59e0b', '#6b7280', '#8b5cf6'])
            )])
            
            fig.update_layout(
                title=f"NL2SQL 失败原因分析（共 {analysis['total']} 条，失败 {analysis['failed']} 个）",
                showlegend=True,
                height=400
            )
            
            return fig
        except ImportError:
            print("[EVALUATION] Plotly 未安装，无法生成图表")
            return None
        except Exception as e:
            print(f"[EVALUATION] 生成 NL2SQL 失败原因图表时出错: {e}")
            import traceback
            traceback.print_exc()
            return None


class DbRheoWebApp:
    def __init__(self):
        self.config = None
        self.client = None
        self.chat_history = []
        self.current_session_id = None
        self.available_databases = []
        self.log_collector = LogCollector()  # 日志收集器
        self.baseline_agent = None  # Baseline Agent 实例
        self.evaluation_manager = EvaluationManager()  # 评估管理器

        # 持久化路径
        self.history_dir = Path(__file__).parent / ".gradio_history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.current_history_file = None
        self.saved_history_count = 0  # 跟踪已保存的消息数

        # 初始化配置和客户端
        self._initialize()
        self._scan_databases()
        self._initialize_baseline_agent()  # 初始化 Baseline Agent
        
    def _initialize(self):
        """初始化配置和客户端"""
        try:
            # 使用 TestDatabaseConfig 明确指定数据库（与 CLI 一致）
            db_path = Path(__file__).parent / "db" / "vehicle_sales.db"
            self.config = TestDatabaseConfig.create_with_sqlite_database(str(db_path))

            # 显示配置信息
            print("\n" + "="*60)
            print("DbRheo Config Info")
            print("="*60)

            # 数据库配置
            db_url = self.config.get("database_url", "")
            print(f"[DB] Database: {db_url}")

            # API Key 配置
            api_keys = {
                "Google Gemini": os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
                "OpenAI": os.getenv("OPENAI_API_KEY"),
                "Claude/Anthropic": os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY"),
                "Ali Bailian": os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALI_BAILIAN_API_KEY")
            }

            has_api_key = False
            for name, key in api_keys.items():
                if key and key != "{your_" + name.lower().split()[0].lower() + "_api_key_here}":
                    # 简单检查不是默认占位符
                    print(f"[API] {name}: OK")
                    has_api_key = True
                else:
                    print(f"[API] {name}: Not configured")

            if not has_api_key:
                print("\n[WARN] No API Key configured")
                print("[WARN] AI chat will not work")
                print("[WARN] SQL execution still available")
            else:
                print(f"[OK] AI chat available")

            # 模型配置
            model = self.config.get("model", "gemini-2.5-flash")
            print(f"[MODEL] Default: {model}")

            print("="*60 + "\n")

            self.client = DatabaseClient(self.config)
            print("[OK] DbRheo client initialized\n")

            # 设置日志回调
            self._setup_logging_callback()

        except Exception as e:
            print(f"[ERROR] Init failed: {e}")
            import traceback
            traceback.print_exc()
            # 不抛出异常，让应用仍能启动（只是 AI 功能不可用）

    def _setup_logging_callback(self):
        """设置日志回调，捕获scheduler的输出"""
        if not self.client or not hasattr(self.client, 'tool_scheduler'):
            return

        scheduler = self.client.tool_scheduler

        # 保存原始回调
        original_on_all_complete = scheduler.on_all_tools_complete

        # 创建新的回调，添加日志
        def logging_callback(tool_calls):
            self.log_collector.add("Scheduler", f"_attempt_execution_of_scheduled_calls: {len(tool_calls)} tools total")

            # 记录每个工具的状态
            for idx, tc in enumerate(tool_calls):
                tool_name = tc.request.name if hasattr(tc, 'request') else 'unknown'
                call_id = tc.request.call_id if hasattr(tc, 'request') else ''
                status = tc.status
                self.log_collector.add("Scheduler", f"  Tool[{idx}] {tool_name} - {call_id} - status: {status}")

                # 记录工具状态变化
                if status == 'scheduled':
                    self.log_collector.add("ToolHandler", f"⏳ {tool_name} - Pending")
                    # 记录工具参数（如果是scheduled状态）
                    if hasattr(tc, 'request') and hasattr(tc.request, 'args'):
                        args = tc.request.args
                        # 记录SQL等关键参数
                        for key, value in args.items():
                            if key.lower() in ['sql', 'query']:
                                sql_text = str(value)
                                # 如果SQL太长，截断显示
                                if len(sql_text) > 300:
                                    sql_display = sql_text[:300] + "..."
                                else:
                                    sql_display = sql_text
                                self.log_collector.add("ToolHandler", f"  Executing SQL:")
                                # 格式化SQL，每行缩进
                                for line in sql_display.split('\n'):
                                    self.log_collector.add("ToolHandler", f"    {line}")
                elif status == 'success':
                    self.log_collector.add("ToolHandler", f"✓ {tool_name} - Success")
                elif status == 'error':
                    self.log_collector.add("Error", f"✗ {tool_name} - Error")

            # 调用原始回调
            if original_on_all_complete:
                original_on_all_complete(tool_calls)

        # 设置新回调
        scheduler.on_all_tools_complete = logging_callback
    
    def _initialize_baseline_agent(self):
        """初始化 Baseline Agent"""
        try:
            from baseline_agent_enhanced import EnhancedBaselineAgent

            csv_path = Path(__file__).parent / "baseline" / "数据源_销量.csv"
            if not csv_path.exists():
                print(f"[WARN] Baseline Agent CSV not found: {csv_path}")
                return

            self.baseline_agent = EnhancedBaselineAgent(str(csv_path))
            print(f"[OK] Baseline Agent initialized")
        except Exception as e:
            print(f"[WARN] Baseline Agent init failed: {e}")

    def _scan_databases(self):
        """扫描可用的数据库文件"""
        db_dir = Path(__file__).parent / "db"
        if db_dir.exists():
            self.available_databases = [f.name for f in db_dir.glob("*.db")]
            print(f"[OK] Found databases: {', '.join(self.available_databases)}")
        else:
            print("[WARN] db directory not found")
            self.available_databases = []
    
    def execute_sql(self, sql, database="默认数据库"):
        """执行 SQL 查询"""
        if not sql or sql.strip() == "":
            return None, "请输入 SQL 语句"
        
        try:
            from dbrheo.adapters.connection_manager import DatabaseConnectionManager
            from dbrheo.adapters.sqlite_adapter import SQLiteAdapter
            import asyncio
            
            async def _execute():
                # 如果选择了特定的数据库，创建新的适配器
                if database and database != "默认数据库":
                    db_path = Path(__file__).parent / "db" / database
                    if db_path.exists():
                        adapter = SQLiteAdapter({"database": str(db_path)})
                        await adapter.connect()
                        try:
                            result = await adapter.execute_query(sql)
                            if result["success"]:
                                data = result.get("data", [])
                                columns = result.get("columns", [])
                                if data and columns:
                                    df = pd.DataFrame(data, columns=columns)
                                    return df, f"✓ 查询成功（{database}），返回 {len(data)} 行数据"
                                else:
                                    return None, f"✓ 查询成功（{database}），但无数据返回"
                            else:
                                return None, f"✗ 查询失败（{database}）: {result.get('error', '未知错误')}"
                        finally:
                            await adapter.disconnect()
                    else:
                        return None, f"✗ 数据库文件不存在: {database}"
                else:
                    # 使用默认数据库
                    manager = DatabaseConnectionManager(self.config)
                    adapter = await manager.get_connection()
                    
                    result = await adapter.execute_query(sql)
                    
                    if result["success"]:
                        data = result.get("data", [])
                        columns = result.get("columns", [])
                        if data and columns:
                            df = pd.DataFrame(data, columns=columns)
                            return df, f"✓ 查询成功（默认数据库），返回 {len(data)} 行数据"
                        else:
                            return None, "✓ 查询成功（默认数据库），但无数据返回"
                    else:
                        return None, f"✗ 查询失败: {result.get('error', '未知错误')}"
            
            df, message = asyncio.run(_execute())
            return df, message
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            return None, f"✗ 执行出错: {str(e)}\n\n{error_detail}"
    
    async def chat_with_ai_stream(self, message, history):
        """与 AI 对话 - 流式输出（生成器）"""
        # 清空旧日志
        self.log_collector.clear()
        self.log_collector.add("Chat", f"开始对话: {message}")

        if not self.client:
            yield "⚠️ 客户端未初始化，请检查配置（需要 API Key）"
            return

        if not message or message.strip() == "":
            yield "请输入问题"
            return

        try:
            from dbrheo.types.core_types import SimpleAbortSignal

            signal = SimpleAbortSignal()
            session_id = self.current_session_id or f"session_{id(self)}"
            self.current_session_id = session_id

            self.log_collector.add("Chat", f"会话ID: {session_id}")
            self.log_collector.add("Chat", f"历史记录数: {len(self.chat_history)}")

            # 获取历史记录信息用于日志
            if self.chat_history:
                total_chars = sum(len(msg.get('content', '')) for msg in self.chat_history)
                self.log_collector.add("Chat", f"总消息: {len(self.chat_history)}, 总字符: {total_chars}")

            # 发送请求
            self.log_collector.add("Client", f"send_message_stream called with prompt_id={session_id}")

            response_stream = self.client.send_message_stream(
                request=message,
                signal=signal,
                prompt_id=session_id,
                turns=100
            )

            self.log_collector.add("Client", "开始流式响应")

            # 流式输出响应（简化版：实时输出）
            response_parts = []
            tool_calls = []
            chunk_count = 0

            async for chunk in response_stream:
                chunk_count += 1

                # 记录chunk类型（每50个chunk或特殊类型记录一次）
                chunk_type = chunk.get("type", "Unknown")
                if chunk_count % 50 == 0 or chunk_type in ["ToolCallRequest", "Error", "Thought"]:
                    self.log_collector.add("Stream", f"Chunk #{chunk_count}: {chunk_type}")

                # 处理文本内容（来自turn.py的Content类型）
                if chunk.get("type") == "Content":
                    content = chunk.get("value", "")
                    if content:
                        response_parts.append(content)
                        # 直接输出，不缓冲
                        yield content
                # 处理思考内容
                elif chunk.get("type") == "Thought":
                    thought = chunk.get("value", "")
                    if thought:
                        self.log_collector.add("Thought", thought)
                # 处理错误
                elif chunk.get("type") == "Error":
                    error_msg = chunk.get("value", "未知错误")
                    self.log_collector.add("Error", error_msg)
                    yield f"\n✗ 错误: {error_msg}"
                # 处理工具调用
                elif chunk.get("type") == "ToolCallRequest":
                    tool_value = chunk.get('value')
                    if tool_value:
                        tool_name = getattr(tool_value, 'name',
                                       tool_value.get('name', 'unknown') if isinstance(tool_value, dict) else 'unknown')
                        tool_calls.append(tool_name)

                        # 记录工具调用（与CLI一致）
                        self.log_collector.add("ToolHandler", f"Tool request: {tool_name}")
                        self.log_collector.add("ToolHandler", f"⏳ {tool_name} - Pending")

                        # 获取工具参数
                        args = getattr(tool_value, 'args',
                                  tool_value.get('args', {}) if isinstance(tool_value, dict) else {})

                        # 记录SQL等关键参数
                        for key, value in args.items():
                            if key.lower() in ['sql', 'query']:
                                sql_text = str(value)
                                # 如果SQL太长，截断显示
                                if len(sql_text) > 300:
                                    sql_display = sql_text[:300] + "..."
                                else:
                                    sql_display = sql_text
                                self.log_collector.add("ToolHandler", f"  Executing SQL:")
                                # 格式化SQL，每行缩进
                                for line in sql_display.split('\n'):
                                    self.log_collector.add("ToolHandler", f"    {line}")

            response_text = "".join(response_parts)
            self.log_collector.add("Chat", f"收到 {chunk_count} 个chunks, 响应长度: {len(response_text)}")

            # 如果有工具调用，添加提示
            if tool_calls:
                tool_info = f"\n\n(使用了工具: {', '.join(tool_calls)})"
                response_text += tool_info
                self.log_collector.add("ToolHandler", f"使用的工具: {', '.join(tool_calls)}")
                yield tool_info

            # 更新历史记录（新格式）
            self.chat_history.append({"role": "user", "content": message})
            self.chat_history.append({"role": "assistant", "content": response_text})

            self.log_collector.add("History", "对话已保存到历史记录")

            # 持久化保存
            self._save_history()

            self.log_collector.add("Chat", "对话完成")

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.log_collector.add("Error", f"{str(e)}")
            yield f"✗ 对话出错: {str(e)}"
    
    def get_database_schema(self):
        """获取数据库结构"""
        try:
            from dbrheo.adapters.connection_manager import DatabaseConnectionManager
            import asyncio
            
            async def _get_schema():
                manager = DatabaseConnectionManager(self.config)
                adapter = await manager.get_connection()
                
                result = await adapter.get_schema_info()
                
                if result["success"]:
                    schema = result["schema"]
                    tables = schema.get("tables", {})
                    
                    # 格式化显示
                    table_info = []
                    for table_name, columns in tables.items():
                        col_str = ", ".join([f"{col['name']} ({col['type']})" for col in columns])
                        table_info.append(f"**{table_name}**: {col_str}")
                    
                    return "\n\n".join(table_info)
                else:
                    return f"获取失败: {result.get('error', '未知错误')}"
            
            return asyncio.run(_get_schema())
            
        except Exception as e:
            return f"✗ 查询出错: {str(e)}"
    
    def clear_history(self):
        """清空对话历史"""
        # 保存当前对话后再清空
        if self.chat_history:
            self._save_history()

        self.chat_history = []
        self.current_session_id = None
        self.saved_history_count = 0  # 重置保存计数器
        # Gradio Chatbot 使用新格式 [{"role": "user", "content": "..."}, ...]
        return [], "✓ 对话历史已清空"

    def _save_history(self):
        """保存对话历史到文件（增量保存）"""
        if not self.chat_history:
            return

        # 使用当前会话ID作为文件名
        if not self.current_history_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_history_file = self.history_dir / f"session_{timestamp}.jsonl"
            # 新文件时重置计数器
            self.saved_history_count = 0

        try:
            # 只保存新的对话（增量保存）
            new_messages = self.chat_history[self.saved_history_count:]

            if not new_messages:
                return  # 没有新消息需要保存

            with open(self.current_history_file, 'a', encoding='utf-8') as f:
                for msg in new_messages:
                    # 保存消息（新格式）
                    log_entry = {
                        'timestamp': datetime.now().isoformat(),
                        'role': msg['role'],
                        'content': msg['content']
                    }
                    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

            # 更新已保存计数
            self.saved_history_count = len(self.chat_history)

            print(f"[HISTORY] 已保存 {len(new_messages)} 条消息到: {self.current_history_file}")
        except Exception as e:
            print(f"[HISTORY] 保存失败: {e}")

    def _get_history_files(self):
        """获取所有历史文件"""
        history_files = []
        if self.history_dir.exists():
            for file in sorted(self.history_dir.glob("session_*.jsonl"), reverse=True):
                # 提取时间戳
                name = file.stem  # session_20250113_120000
                try:
                    timestamp = datetime.strptime(name.replace("session_", ""), "%Y%m%d_%H%M%S")
                    history_files.append({
                        'file': file,
                        'timestamp': timestamp,
                        'name': name
                    })
                except:
                    continue
        return history_files

    def delete_history(self, file_name):
        """删除指定的历史会话文件"""
        file_path = self.history_dir / f"{file_name}.jsonl"
        try:
            if file_path.exists():
                file_path.unlink()
                print(f"[HISTORY] 已删除: {file_path}")
                return True, f"✓ 已删除会话: {file_name}"
            else:
                return False, f"❌ 文件不存在: {file_name}"
        except Exception as e:
            print(f"[HISTORY] 删除失败: {e}")
            return False, f"✗ 删除失败: {str(e)}"

    def load_question_csv(self):
        """加载问题和答案CSV文件"""
        csv_path = Path(__file__).parent / "test" / "answer" / "automotive_answers_100.csv"
        try:
            if csv_path.exists():
                questions = []  # 带序号的问题列表
                qa_dict = {}  # 问题到答案的映射
                idx = 1

                # 直接逐行读取，避免CSV解析器因为特殊字符分割答案
                with open(csv_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    current_question = None

                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue

                        if line.startswith("问题："):
                            # 遇到新问题，保存当前问题
                            current_question = line.replace("问题：", "").strip()

                        elif line.startswith("答案："):
                            # 提取答案（完整行，不进行任何分割）
                            current_answer = line.replace("答案：", "").strip()

                            # 配对成功
                            if current_question is not None:
                                # 添加序号
                                question_with_idx = f"{idx}. {current_question}"
                                questions.append(question_with_idx)
                                qa_dict[question_with_idx] = current_answer
                                idx += 1
                                current_question = None

                print(f"[QUESTIONS] 加载了 {len(questions)} 个问题和答案")
                return questions, qa_dict
            else:
                print(f"[QUESTIONS] 文件不存在: {csv_path}")
                return [], {}
        except Exception as e:
            print(f"[QUESTIONS] 加载失败: {e}")
            import traceback
            traceback.print_exc()
            return [], {}

    def _load_history_file(self, file_path):
        """加载历史文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                messages = []
                for line in f:
                    if line.strip():
                        log_entry = json.loads(line)
                        messages.append(log_entry)
                return messages
        except Exception as e:
            print(f"[HISTORY] 加载失败: {e}")
            return []

    def get_history_list(self):
        """获取历史会话列表"""
        history_files = self._get_history_files()

        if not history_files:
            return "暂无历史会话"

        # 格式化输出
        lines = ["### 📚 历史会话列表\n"]
        for idx, hf in enumerate(history_files):
            time_str = hf['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"{idx + 1}. **{hf['name']}** ({time_str})")

        lines.append("\n💡 **使用方法**：在「历史会话」标签页选择要查看的会话")
        return "\n".join(lines)

    def query_baseline_agent(self, question, standard_answer=None):
        """使用 Baseline Agent 查询"""
        if not self.baseline_agent:
            return "⚠️ Baseline Agent 未初始化", "", "", "", ""

        try:
            # 执行查询（verbose=False 避免打印过多日志）
            result = self.baseline_agent.query(question, verbose=False)

            # 格式化输出
            answer = result.get("answer", "")
            conditions = result.get("conditions", {})
            filtered_rows = result.get("filtered_rows", 0)
            tokens = result.get("tokens") or {}
            duration = result.get("duration_ms", 0)
            error = result.get("error", "")

            # 构建详细信息
            details = []
            details.append(f"### 📊 查询详情\n")

            if conditions:
                details.append("**过滤条件：**")
                details.append(f"- 时间范围: {conditions.get('time_start', 'N/A')} ~ {conditions.get('time_end', 'N/A')}")
                details.append(f"- 品牌关键词: {', '.join(conditions.get('brand_keywords', []))}")
                details.append(f"- 车型关键词: {', '.join(conditions.get('model_keywords', []))}")
                details.append(f"- 需要对比: {conditions.get('need_comparison', False)}")
                details.append(f"- 对比期: {conditions.get('comparison_time', 'N/A')}")
                details.append(f"")
                details.append(f"**数据统计：**")
                details.append(f"- 筛选后行数: {filtered_rows}")
                details.append(f"")

            if tokens:
                details.append("**Token 消耗：**")
                details.append(f"- 输入: {tokens.get('prompt', 0)}")
                details.append(f"- 输出: {tokens.get('completion', 0)}")
                details.append(f"- 总计: {tokens.get('total', 0)}")
                details.append(f"")
                details.append(f"**执行时间：** {duration:.2f} ms")
                details.append(f"")

            if not result.get("success"):
                details.append(f"⚠️ **错误：** {error}")
                if result.get("error_analysis"):
                    details.append(f"\n**分析：**\n{result.get('error_analysis')}")

            # 如果提供了标准答案，记录评估
            if standard_answer and answer:
                try:
                    self.evaluation_manager.add_evaluation(
                        question=question,
                        standard_answer=standard_answer,
                        actual_response=answer,
                        agent_type="Baseline"
                    )
                    print(f"[EVALUATION] 已记录 Baseline 评估")
                except Exception as e:
                    print(f"[EVALUATION] 记录评估失败: {e}")

            return answer, "\n".join(details), str(filtered_rows), str(tokens.get('total', 0)), str(duration)

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            return f"✗ 查询出错: {str(e)}\n\n{error_detail}", "", "", "", ""

    def load_history(self, file_name):
        """加载历史会话"""
        file_path = self.history_dir / f"{file_name}.jsonl"
        if not file_path.exists():
            return []  # 返回空列表而不是错误字符串

        messages = self._load_history_file(file_path)

        # 转换为Gradio Chatbot新格式 [{"role": "user", "content": "..."}, ...]
        history = []
        for msg in messages:
            role = msg['role']
            # 将 'bot' 角色转换为 'assistant'
            if role == 'bot':
                role = 'assistant'
            history.append({
                "role": role,
                "content": msg['content']
            })

        return history

    def _get_stats_display(self):
        """生成统计信息的显示文本"""
        stats = self.evaluation_manager.get_statistics()

        lines = [
            f"**总评估数：** {stats['total']}",
            f"**正确数：** {stats['correct']}",
            f"**准确率：** {stats['accuracy']:.2f}%"
        ]

        # 添加各Agent类型的统计
        if stats['by_agent']:
            lines.append("\n**按Agent类型：**\n")
            for agent_type, agent_stats in stats['by_agent'].items():
                lines.append(f"- **{agent_type}**:")
                lines.append(f"  - 总数: {agent_stats['total']}")
                lines.append(f"  - 正确: {agent_stats['correct']}")
                lines.append(f"  - 准确率: {agent_stats['accuracy']:.2f}%")

        return "\n".join(lines)

    def _get_dashboard_display(self):
        """生成准确率看板的显示文本（按Agent分类，每个问题只取最新，最多100条）"""
        stats = self.evaluation_manager.get_statistics_by_agent_latest()
        
        # 获取 NL2SQL 和 Baseline 的失败原因分析
        nl2sql_failure = self.evaluation_manager.analyze_nl2sql_failures()
        baseline_failure = self.evaluation_manager.analyze_baseline_failures()

        # 生成进度条
        def create_progress_bar(accuracy):
            # 创建简单的ASCII进度条
            filled = int(accuracy / 10)
            bar = "█" * filled + "░" * (10 - filled)
            return f"{bar} {accuracy:.1f}%"

        lines = [
            "### 📊 方案准确率看板",
            "",
            "**说明**：每个问题只取最新结果，按时间从后往前，最多统计100条",
            ""
        ]

        # NL2SQL 看板
        nl2sql_stats = stats['NL2SQL']
        lines.append("#### 💬 NL2SQL Agent")
        lines.append(f"- 总问题数：{nl2sql_stats['total']}")
        lines.append(f"- 正确数：{nl2sql_stats['correct']}")
        lines.append(f"- 失败数：{nl2sql_stats['total'] - nl2sql_stats['correct']}")
        lines.append(f"- 准确率：{create_progress_bar(nl2sql_stats['accuracy'])}")
        
        # NL2SQL 失败原因
        if nl2sql_stats['total'] - nl2sql_stats['correct'] > 0:
            lines.append("- **失败原因分布**：")
            for reason, count in nl2sql_failure['failure_reasons'].items():
                if count > 0:
                    lines.append(f"  - {reason}：{count}")
        lines.append("")

        # Baseline 看板
        baseline_stats = stats['Baseline']
        lines.append("#### 📈 Baseline Agent")
        lines.append(f"- 总问题数：{baseline_stats['total']}")
        lines.append(f"- 正确数：{baseline_stats['correct']}")
        lines.append(f"- 失败数：{baseline_stats['total'] - baseline_stats['correct']}")
        lines.append(f"- 准确率：{create_progress_bar(baseline_stats['accuracy'])}")
        
        # Baseline 失败原因
        if baseline_stats['total'] - baseline_stats['correct'] > 0:
            lines.append("- **失败原因分布**：")
            for reason, count in baseline_failure['failure_reasons'].items():
                if count > 0:
                    lines.append(f"  - {reason}：{count}")
        lines.append("")

        # 胜者
        if stats['winner']:
            if stats['winner'] == '平局':
                lines.append("#### 🏆 对比结果")
                lines.append("**平局**：两个Agent准确率相同")
            else:
                lines.append("#### 🏆 对比结果")
                lines.append(f"**胜者：{stats['winner']}** ✨")
                lines.append(f"- NL2SQL: {nl2sql_stats['accuracy']:.1f}%")
                lines.append(f"- Baseline: {baseline_stats['accuracy']:.1f}%")
        else:
            lines.append("#### 🏆 对比结果")
            lines.append("⚠️ 暂无足够数据进行对比")

        return "\n".join(lines)
    
    def create_interface(self):
        """创建 Gradio 界面"""
        with gr.Blocks(title="DbRheo - 智能数据库 Agent") as app:
            gr.Markdown("# 🚗 DbRheo - 智能数据库 Agent")
            gr.Markdown("基于 AI 的数据库查询工具，支持自然语言对话和 SQL 执行")
            
            with gr.Tabs():
                # Tab 1: NL2SQL Agent
                with gr.Tab("💬 NL2SQL Agent"):
                    with gr.Row():
                        with gr.Column(scale=3):
                            # 快速问题选择
                            questions, qa_dict = self.load_question_csv()

                            question_dropdown = gr.Dropdown(
                                label="选择预设问题（可选）",
                                choices=questions,
                                info="从测试问题列表中选择，也可以自定义输入"
                            )

                            # 标准答案显示
                            reference_answer = gr.Textbox(
                                label="标准答案（参考）",
                                placeholder="选择问题后显示标准答案",
                                interactive=False,
                                lines=2
                            )

                            chatbot = gr.Chatbot(
                                label="对话历史",
                                height=350
                            )
                            with gr.Row():
                                msg_input = gr.Textbox(
                                    label="输入问题",
                                    placeholder="例如：2023年比亚迪的总销量是多少？",
                                    scale=4
                                )
                                send_btn = gr.Button("发送", scale=1, variant="primary")

                            with gr.Row():
                                clear_btn = gr.Button("清空历史", size="sm")

                        with gr.Column(scale=1):
                            gr.Markdown("### 💡 提示")
                            tips = gr.Markdown(
                                """
                                - 支持自然语言查询数据库
                                - 可以问销量、同比、环比等问题
                                - 支持 SQL 语句的生成和执行

                                **示例问题：**
                                - 2023年比亚迪的总销量是多少？
                                - 一汽大众在2023年6月的销量同比增长是多少？
                                - 显示所有车型表的结构
                                """
                            )

                            # 日志面板
                            with gr.Accordion("📋 交互流程日志", open=False):
                                log_output = gr.Textbox(
                                    label="日志输出",
                                    value="等待对话开始...",
                                    lines=25,
                                    max_lines=40,
                                    interactive=False,
                                    placeholder="日志将在这里显示",
                                    elem_id="log_output"
                                )

                                # 添加日志刷新按钮
                                refresh_logs_btn = gr.Button("刷新日志", size="sm", scale=1)
                                clear_logs_btn = gr.Button("清空日志", size="sm", scale=1)

                    # 问题选择联动：选择问题后自动填充到输入框和显示答案
                    def on_question_select(question):
                        # 去掉序号
                        question_text = question.split(". ", 1)[1] if ". " in question else question
                        answer = qa_dict.get(question, "")
                        return question_text, answer

                    question_dropdown.change(
                        on_question_select,
                        inputs=[question_dropdown],
                        outputs=[msg_input, reference_answer]
                    )
                    
                    async def on_send(message, history):
                        if not message.strip():
                            return history, ""

                        # 检查历史记录长度（降低阈值，更早提示）
                        if len(history) > 50:
                            error_msg = "⚠️ 提示：对话历史较长（超过50轮），建议清空历史以获得更好的响应质量"
                            history = history + [{"role": "user", "content": message}, {"role": "assistant", "content": error_msg}]
                            return history, ""

                        # 添加用户消息
                        history = history + [{"role": "user", "content": message}]

                        # 非流式：收集完整响应
                        bot_message = ""
                        try:
                            async for chunk in self.chat_with_ai_stream(message, history):
                                bot_message += chunk

                        except Exception as e:
                            print(f"[ERROR] 响应异常: {e}")
                            bot_message = f"⚠️ 发生错误: {str(e)}"

                        # 添加到历史
                        history[-1] = {"role": "assistant", "content": bot_message}

                        # 记录评估
                        try:
                            standard_answer = None
                            for question_key, answer in qa_dict.items():
                                question_text = question_key.split(". ", 1)[1] if ". " in question_key else question_key
                                if question_text == message:
                                    standard_answer = answer
                                    break

                            if standard_answer and bot_message:
                                self.evaluation_manager.add_evaluation(
                                    question=message,
                                    standard_answer=standard_answer,
                                    actual_response=bot_message,
                                    agent_type="NL2SQL"
                                )
                        except Exception as e:
                            print(f"[EVALUATION] 记录评估失败: {e}")

                        return history, ""

                    def on_refresh_logs():
                        """刷新日志显示"""
                        return self.log_collector.get_formatted_logs()

                    def on_clear_logs():
                        """清空日志"""
                        return self.log_collector.clear()

                    def on_clear():
                        history, _ = self.clear_history()
                        # 返回空列表，Gradio Chatbot 新格式
                        return history

                    send_btn.click(
                        on_send,
                        inputs=[msg_input, chatbot],
                        outputs=[chatbot, msg_input]
                    )

                    msg_input.submit(
                        on_send,
                        inputs=[msg_input, chatbot],
                        outputs=[chatbot, msg_input]
                    )
                    
                    clear_btn.click(
                        on_clear,
                        outputs=[chatbot]
                    )

                    refresh_logs_btn.click(
                        on_refresh_logs,
                        outputs=[log_output]
                    )

                    clear_logs_btn.click(
                        on_clear_logs,
                        outputs=[log_output]
                    )
                
                # Tab 2: SQL 执行
                with gr.Tab("🔍 SQL 执行"):
                    with gr.Row():
                        with gr.Column(scale=2):
                            database_dropdown = gr.Dropdown(
                                label="选择数据库",
                                choices=["默认数据库"] + self.available_databases,
                                value="默认数据库",
                                info="选择要查询的数据库文件"
                            )
                            sql_input = gr.Textbox(
                                label="SQL 语句",
                                placeholder="选择下方的示例查询",
                                lines=10,
                                elem_id="sql_input"
                            )
                            with gr.Row():
                                example_btn = gr.Button("示例查询", variant="secondary")
                                execute_btn = gr.Button("执行 SQL", variant="primary")
                        
                        with gr.Column(scale=3):
                            result_output = gr.DataFrame(label="查询结果")
                            status_output = gr.Textbox(label="执行状态")
                    
                    # 示例查询功能 - 基于测试问题集
                    example_sqls = [
                        # 1. 月销量查询
                        "-- 1. 月销量查询：2023-06，一汽大众揽境的销量是多少？\nSELECT brand, model, date, sales_volume\nFROM vehicle_sales\nWHERE brand = '一汽大众'\n  AND model = '揽境'\n  AND date LIKE '2023-06%';",
                        
                        # 2. 品牌月销量变化
                        "-- 2. 品牌月销量变化：一汽大众在2023年每个月的销量变化情况\nSELECT substr(date, 1, 7) as month,\n       SUM(sales_volume) as total_sales\nFROM vehicle_sales\nWHERE brand = '一汽大众'\n  AND date BETWEEN '2023-01-01' AND '2023-12-31'\nGROUP BY substr(date, 1, 7)\nORDER BY month;",
                        
                        # 3. 年销量总和
                        "-- 3. 年销量总和：一汽大众揽境在2022全年的销量总和\nSELECT brand, model, SUM(sales_volume) as total_sales\nFROM vehicle_sales\nWHERE brand = '一汽大众'\n  AND model = '揽境'\n  AND date BETWEEN '2022-01-01' AND '2022-12-31'\nGROUP BY brand, model;",
                        
                        # 4. 时间区间销量
                        "-- 4. 时间区间销量：一汽大众高尔夫A8在2023-01月到2023-06月之间的销量总和\nSELECT brand, model, SUM(sales_volume) as total_sales\nFROM vehicle_sales\nWHERE brand = '一汽大众'\n  AND model = '高尔夫A8'\n  AND date BETWEEN '2023-01-01' AND '2023-06-30'\nGROUP BY brand, model;",
                        
                        # 5. 同比增长
                        "-- 5. 同比增长：一汽大众在2023-06月的销量同比增长\nSELECT\n  current_year.month,\n  current_year.brand,\n  current_year.sales_volume as current_sales,\n  last_year.sales_volume as last_year_sales,\n  ROUND((current_year.sales_volume - last_year.sales_volume) * 100.0 / last_year.sales_volume, 2) as yoy_growth_percent\nFROM (\n  SELECT substr(date, 1, 7) as month, brand, SUM(sales_volume) as sales_volume\n  FROM vehicle_sales\n  WHERE brand = '一汽大众' AND date LIKE '2023-06%'\n  GROUP BY substr(date, 1, 7), brand\n) current_year\nLEFT JOIN (\n  SELECT substr(date, 1, 7) as month, brand, SUM(sales_volume) as sales_volume\n  FROM vehicle_sales\n  WHERE brand = '一汽大众' AND date LIKE '2022-06%'\n  GROUP BY substr(date, 1, 7), brand\n) last_year ON current_year.brand = last_year.brand;",
                        
                        # 6. 环比增长
                        "-- 6. 环比增长：一汽大众在2023-06月的销量环比增长\nWITH monthly_sales AS (\n  SELECT substr(date, 1, 7) as month, SUM(sales_volume) as sales_volume\n  FROM vehicle_sales\n  WHERE brand = '一汽大众' AND date BETWEEN '2023-01-01' AND '2023-12-31'\n  GROUP BY substr(date, 1, 7)\n)\nSELECT\n  current.month,\n  current.sales_volume as current_sales,\n  previous.sales_volume as previous_sales,\n  ROUND((current.sales_volume - previous.sales_volume) * 100.0 / previous.sales_volume, 2) as mom_growth_percent\nFROM monthly_sales current\nLEFT JOIN monthly_sales previous ON substr(current.month, 6, 7) = substr(previous.month, 6, 7) + 1\nWHERE current.month = '2023-06';",
                        
                        # 7. 销量最好的品牌
                        "-- 7. 某时间段销量最好的品牌：2023-12，文中所列品牌中哪家销量最好\nSELECT brand, SUM(sales_volume) as total_sales\nFROM vehicle_sales\nWHERE date LIKE '2023-12%'\nGROUP BY brand\nORDER BY total_sales DESC\nLIMIT 5;",
                        
                        # 8. 销量最好的车型
                        "-- 8. 某时间段销量最好的车型：2023-12，销量最高的具体车型\nSELECT brand, model, SUM(sales_volume) as total_sales\nFROM vehicle_sales\nWHERE date LIKE '2023-12%'\nGROUP BY brand, model\nORDER BY total_sales DESC\nLIMIT 10;",
                        
                        # 9. 多车型销量对比
                        "-- 9. 多车型销量对比：2023-12，一汽大众和比亚迪的销量对比\nSELECT brand, SUM(sales_volume) as total_sales\nFROM vehicle_sales\nWHERE brand IN ('一汽大众', '比亚迪') AND date LIKE '2023-12%'\nGROUP BY brand;",
                        
                        # 10. 查看数据概览
                        "-- 10. 数据概览：查看vehicle_sales表结构\nSELECT * FROM vehicle_sales LIMIT 10;"
                    ]
                    current_example = [0]
                    
                    def on_example():
                        idx = current_example[0]
                        sql = example_sqls[idx % len(example_sqls)]
                        current_example[0] = idx + 1
                        return sql
                    
                    example_btn.click(
                        on_example,
                        outputs=[sql_input]
                    )
                    
                    execute_btn.click(
                        self.execute_sql,
                        inputs=[sql_input, database_dropdown],
                        outputs=[result_output, status_output]
                    )
                
                # Tab 3: 数据库结构
                with gr.Tab("📊 数据库结构"):
                    with gr.Row():
                        refresh_btn = gr.Button("刷新结构", variant="primary")
                    
                    schema_output = gr.Markdown(
                        label="数据库表结构",
                        value=self.get_database_schema()
                    )
                    
                    refresh_btn.click(
                        self.get_database_schema,
                        outputs=[schema_output]
                    )
                
                # Tab 4: 快速查询
                with gr.Tab("⚡ 快速查询"):
                    gr.Markdown("### 常用查询示例")
                    
                    with gr.Row():
                        query1 = gr.Button("显示一汽大众揽境2023年6月销量")
                        query2 = gr.Button("比亚迪2023年总销量")
                        query3 = gr.Button("一汽大众2023年月销量变化")
                    
                    with gr.Row():
                        query4 = gr.Button("2023年12月销量最高车型")
                        query5 = gr.Button("一汽大众vs比亚迪销量对比")
                    
                    quick_result = gr.Markdown("点击上方按钮执行快速查询")
                    
                    # 为每个按钮定义单独的函数，避免 lambda 闭包问题
                    async def on_query1():
                        message = "2023年6月，一汽大众揽境的销量是多少？"
                        response = ""
                        async for chunk in self.chat_with_ai_stream(message, []):
                            response += chunk
                        return f"正在查询: {message}\n\n{response}"

                    async def on_query2():
                        message = "比亚迪在2023年的总销量是多少？"
                        response = ""
                        async for chunk in self.chat_with_ai_stream(message, []):
                            response += chunk
                        return f"正在查询: {message}\n\n{response}"

                    async def on_query3():
                        message = "一汽大众在2023年每个月的销量变化情况是多少？"
                        response = ""
                        async for chunk in self.chat_with_ai_stream(message, []):
                            response += chunk
                        return f"正在查询: {message}\n\n{response}"

                    async def on_query4():
                        message = "2023年12月，销量最高的具体车型是哪款？"
                        response = ""
                        async for chunk in self.chat_with_ai_stream(message, []):
                            response += chunk
                        return f"正在查询: {message}\n\n{response}"

                    async def on_query5():
                        message = "2023年12月，一汽大众和比亚迪的销量对比如何？"
                        response = ""
                        async for chunk in self.chat_with_ai_stream(message, []):
                            response += chunk
                        return f"正在查询: {message}\n\n{response}"

                    query1.click(on_query1, outputs=[quick_result])
                    query2.click(on_query2, outputs=[quick_result])
                    query3.click(on_query3, outputs=[quick_result])
                    query4.click(on_query4, outputs=[quick_result])
                    query5.click(on_query5, outputs=[quick_result])

                # Tab 5: Baseline Agent
                with gr.Tab("📈 Baseline Agent"):
                    gr.Markdown("### Baseline Agent - LLM生成过滤条件")
                    gr.Markdown("**方案说明**：基于CSV文件的智能查询方案：LLM生成过滤条件 → Pandas过滤 → LLM分析")
                    gr.Markdown("**与DbRheo Agent的区别**：")
                    gr.Markdown("- Baseline Agent：直接读取CSV，适合离线场景，无需数据库")
                    gr.Markdown("- DbRheo Agent：使用SQL查询数据库，适合在线场景，支持复杂查询")

                    with gr.Row():
                        with gr.Column(scale=2):
                            # 加载测试集问题
                            baseline_questions, baseline_qa_dict = self.load_question_csv()

                            question_dropdown_baseline = gr.Dropdown(
                                label="选择预设问题（可选）",
                                choices=baseline_questions,
                                info="从测试问题列表中选择，也可以自定义输入"
                            )

                            # 标准答案显示
                            baseline_reference_answer = gr.Textbox(
                                label="标准答案（参考）",
                                placeholder="选择问题后显示标准答案",
                                interactive=False,
                                lines=2
                            )

                            question_input_baseline = gr.Textbox(
                                label="输入问题",
                                placeholder="例如：2023年比亚迪的总销量是多少？",
                                lines=3
                            )

                            with gr.Row():
                                query_baseline_btn = gr.Button("查询", variant="primary")
                                clear_baseline_btn = gr.Button("清空", variant="secondary")

                            # 快速问题按钮
                            gr.Markdown("**快速查询：**")
                            with gr.Row():
                                b_query1 = gr.Button("2023-06，一汽大众揽境的销量", size="sm")
                                b_query2 = gr.Button("比亚迪在2023年的总销量", size="sm")
                                b_query3 = gr.Button("一汽大众2023年月销量变化", size="sm")

                        with gr.Column(scale=3):
                            # 答案输出
                            baseline_answer = gr.Markdown(
                                label="答案",
                                value="等待查询..."
                            )

                            # 详细信息
                            with gr.Accordion("📋 详细信息", open=True):
                                baseline_details = gr.Markdown(
                                    label="查询详情",
                                    value=""
                                )

                            # 统计信息
                            with gr.Row():
                                baseline_rows = gr.Textbox(label="筛选行数", value="", interactive=False)
                                baseline_tokens = gr.Textbox(label="Token消耗", value="", interactive=False)
                                baseline_duration = gr.Textbox(label="耗时(ms)", value="", interactive=False)

                    # 问题选择联动：选择问题后自动填充到输入框和显示答案
                    def on_baseline_question_select(question):
                        # 去掉序号
                        question_text = question.split(". ", 1)[1] if ". " in question else question
                        answer = baseline_qa_dict.get(question, "")
                        return question_text, answer

                    question_dropdown_baseline.change(
                        on_baseline_question_select,
                        inputs=[question_dropdown_baseline],
                        outputs=[question_input_baseline, baseline_reference_answer]
                    )

                    def on_clear_baseline():
                        return "等待查询...", "", "", "", ""

                    def on_b_query1():
                        return "2023-06，一汽大众揽境的销量是多少？"

                    def on_b_query2():
                        return "比亚迪在2023年的总销量是多少？"

                    def on_b_query3():
                        return "一汽大众在2023年每个月的销量变化情况是多少？"

                    query_baseline_btn.click(
                        self.query_baseline_agent,
                        inputs=[question_input_baseline, baseline_reference_answer],
                        outputs=[baseline_answer, baseline_details, baseline_rows, baseline_tokens, baseline_duration]
                    )

                    clear_baseline_btn.click(
                        on_clear_baseline,
                        outputs=[baseline_answer, baseline_details, baseline_rows, baseline_tokens, baseline_duration]
                    )

                    b_query1.click(
                        on_b_query1,
                        outputs=[question_input_baseline]
                    )

                    b_query2.click(
                        on_b_query2,
                        outputs=[question_input_baseline]
                    )

                    b_query3.click(
                        on_b_query3,
                        outputs=[question_input_baseline]
                    )

                # Tab 6: 评估结果
                with gr.Tab("📊 评估结果"):
                    gr.Markdown("### Agent 查询评估")
                    gr.Markdown("自动记录每次查询的结果，并与标准答案进行比较。支持在线编辑、修改和删除记录。")
                    gr.Markdown("💡 **使用提示**：")
                    gr.Markdown("- 直接点击表格单元格可编辑内容")
                    gr.Markdown("- 编辑完成后点击「保存修改」按钮保存更改")
                    gr.Markdown("- 选中行后可删除记录（手动操作：复制数据到其他工具删除）")

                    with gr.Row():
                        with gr.Column(scale=1):
                            # 准确率看板（按Agent分类）
                            with gr.Accordion("📊 准确率看板（按方案分类）", open=False):
                                dashboard_output = gr.Markdown(
                                    label="准确率看板",
                                    value=self._get_dashboard_display()
                                )
                            
                            # 失败原因分析（使用 Tab 分开显示）
                            with gr.Accordion("📉 失败原因分析", open=True):
                                gr.Markdown("**说明**：分析 NL2SQL 和 Baseline 的失败原因（每个问题只取最新结果，最多100条）")
                                
                                with gr.Tabs():
                                    # NL2SQL 失败原因分析
                                    with gr.Tab("NL2SQL"):
                                        nl2sql_failure_chart = gr.Plot(
                                            label="NL2SQL 失败原因分布（饼图）",
                                            value=self.evaluation_manager.generate_nl2sql_failure_chart()
                                        )
                                    
                                    # Baseline 失败原因分析
                                    with gr.Tab("Baseline"):
                                        failure_chart = gr.Plot(
                                            label="Baseline 失败原因分布（饼图）",
                                            value=self.evaluation_manager.generate_failure_chart()
                                        )
                                    
                                    # 对比图表
                                    with gr.Tab("对比分析"):
                                        comparison_chart = gr.Plot(
                                            label="NL2SQL vs Baseline 对比（柱状图）",
                                            value=self.evaluation_manager.generate_comparison_chart()
                                        )
                                
                                # 刷新图表按钮
                                refresh_charts_btn = gr.Button("刷新图表", variant="secondary", size="sm")

                            # Agent筛选器
                            agent_filter = gr.Radio(
                                label="按方案分类查看",
                                choices=["全部", "NL2SQL", "Baseline"],
                                value="全部",
                                info="选择要查看的Agent类型"
                            )

                            # 问题搜索
                            with gr.Accordion("🔍 搜索问题", open=False):
                                question_search_input = gr.Textbox(
                                    label="搜索问题",
                                    placeholder="输入关键词搜索问题",
                                    lines=2
                                )
                                search_question_btn = gr.Button("搜索", variant="secondary", size="sm")
                                clear_search_btn = gr.Button("清除搜索", size="sm")

                            # 操作按钮
                            with gr.Row():
                                refresh_eval_btn = gr.Button("刷新评估", variant="secondary", size="sm")
                                export_csv_btn = gr.Button("导出CSV", variant="primary", size="sm")
                                export_excel_btn = gr.Button("导出Excel", variant="primary", size="sm")
                                clear_eval_btn = gr.Button("清空评估", variant="stop", size="sm")
                            
                            # 导出状态
                            export_status = gr.Textbox(label="导出状态", visible=True, interactive=False, lines=3)

                        with gr.Column(scale=2):
                            # 评估结果表格
                            eval_dataframe = gr.DataFrame(
                                label="评估记录（按方案分类）- 可编辑",
                                value=self.evaluation_manager.get_evaluation_dataframe(),
                                interactive=True,
                                wrap=True
                            )
                            
                            # 保存和删除按钮
                            with gr.Row():
                                save_changes_btn = gr.Button("💾 保存修改", variant="primary", size="sm")
                                save_status = gr.Textbox(label="保存状态", visible=True, interactive=False, scale=2)
                            
                            # 按ID删除功能
                            with gr.Accordion("🗑️ 删除记录（按ID）", open=False):
                                gr.Markdown("**通过记录ID删除单个或多个评估记录**")
                                with gr.Row():
                                    delete_ids_input = gr.Textbox(
                                        label="要删除的记录ID（多个ID用逗号分隔，如：1,3,5）",
                                        placeholder="输入要删除的记录ID，多个ID用逗号分隔",
                                        scale=3
                                    )
                                    delete_by_id_btn = gr.Button("删除", variant="stop", size="sm")
                                delete_status = gr.Textbox(label="删除状态", visible=True, interactive=False)

                    # 单个问题详情
                    with gr.Accordion("📋 查看问题详情（多次运行记录）", open=False):
                        gr.Markdown("**查看某个问题的所有运行记录**（同一问题可能被运行多次）")

                        with gr.Row():
                            # 问题选择
                            with gr.Column(scale=2):
                                question_search_detail = gr.Textbox(
                                    label="搜索问题（查看详情）",
                                    placeholder="输入问题关键词或指纹"
                                )
                                search_question_detail_btn = gr.Button("搜索问题", variant="secondary", size="sm")

                            # Agent筛选
                            with gr.Column(scale=1):
                                question_agent_filter = gr.Radio(
                                    label="Agent类型",
                                    choices=["全部", "NL2SQL", "Baseline"],
                                    value="全部"
                                )

                        # 问题列表
                        question_list = gr.Dataframe(
                            label="匹配的问题列表",
                            headers=["问题", "运行次数"],
                            datatype=["str", "number"],
                            interactive=False
                        )

                        # 问题详情
                        question_details = gr.DataFrame(
                            label="该问题的所有运行记录",
                            interactive=False,
                            wrap=True
                        )

                        # 问题统计
                        question_stats = gr.Markdown(
                            label="问题统计",
                            value="选择一个问题查看详情"
                        )

                    # 刷新评估结果
                    def on_refresh_eval():
                        df = self.evaluation_manager.get_evaluation_dataframe()
                        dashboard = self._get_dashboard_display()
                        return df, dashboard

                    # Agent筛选
                    def on_agent_filter(agent_type):
                        df = self.evaluation_manager.get_evaluation_dataframe(agent_filter=agent_type)
                        return df

                    # 问题搜索
                    def on_search_question(keyword):
                        df = self.evaluation_manager.get_evaluation_dataframe(question_keyword=keyword)
                        return df

                    # 清除搜索
                    def on_clear_search():
                        df = self.evaluation_manager.get_evaluation_dataframe()
                        return df, ""

                    # 导出CSV
                    def on_export_eval():
                        export_path = self.evaluation_manager.export_csv()
                        if export_path:
                            return f"✓ 已导出到: {export_path}"
                        else:
                            return "⚠️ 没有评估记录可导出"

                    # 清空评估
                    def on_clear_eval():
                        self.evaluation_manager.clear()
                        df = self.evaluation_manager.get_evaluation_dataframe()
                        dashboard = self._get_dashboard_display()
                        return df, dashboard

                    # 保存修改
                    def on_save_changes(edited_df):
                        """保存编辑后的评估记录"""
                        if edited_df is None or len(edited_df) == 0:
                            return "⚠️ 没有可保存的修改"

                        try:
                            # 获取当前所有评估记录
                            current_evals = self.evaluation_manager.evaluations
                            updated_count = 0
                            errors = []

                            # 检查列名（支持大小写兼容）
                            # get_evaluation_dataframe 返回的列名是小写的
                            id_col = 'id' if 'id' in edited_df.columns else 'ID'
                            question_col = 'question' if 'question' in edited_df.columns else '问题'
                            standard_col = 'standard_answer' if 'standard_answer' in edited_df.columns else '标准答案'
                            actual_col = 'actual_answer' if 'actual_answer' in edited_df.columns else '实际答案'
                            correct_col = 'is_correct_str' if 'is_correct_str' in edited_df.columns else '是否正确'

                            # 遍历编辑后的DataFrame
                            for _, row in edited_df.iterrows():
                                eval_id = None
                                try:
                                    eval_id = int(row[id_col])
                                    if pd.isna(eval_id):
                                        continue

                                    # 查找对应的评估记录
                                    eval_record = None
                                    for e in current_evals:
                                        if e['id'] == eval_id:
                                            eval_record = e
                                            break

                                    if eval_record:
                                        # 更新字段
                                        # 标准答案
                                        if not pd.isna(row[standard_col]) and row[standard_col] != eval_record.get('standard_answer'):
                                            eval_record['standard_answer'] = row[standard_col]
                                            updated_count += 1

                                        # 实际答案
                                        if not pd.isna(row[actual_col]) and row[actual_col] != eval_record.get('actual_answer'):
                                            eval_record['actual_answer'] = row[actual_col]
                                            updated_count += 1

                                        # 是否正确
                                        is_correct_str = row[correct_col]
                                        if is_correct_str == '✓ 正确':
                                            is_correct = True
                                        elif is_correct_str == '✗ 错误':
                                            is_correct = False
                                        else:
                                            continue

                                        if is_correct != eval_record.get('is_correct'):
                                            eval_record['is_correct'] = is_correct
                                            updated_count += 1

                                        # 如果修改了标准答案或实际答案，重新计算比较原因
                                        if 'standard_answer' in eval_record or 'actual_answer' in eval_record:
                                            standard_answer = eval_record['standard_answer']
                                            actual_answer = eval_record['actual_answer']
                                            is_correct_new, reason = self.evaluation_manager.compare_answers(
                                                standard_answer, actual_answer
                                            )
                                            eval_record['is_correct'] = is_correct_new
                                            eval_record['comparison_reason'] = reason

                                except Exception as e:
                                    eval_id_str = str(eval_id) if eval_id is not None else "未知"
                                    errors.append(f"记录ID {eval_id_str}: {str(e)}")

                            # 保存到文件
                            if updated_count > 0:
                                self.evaluation_manager._rewrite_evaluation_file()
                                dashboard = self._get_dashboard_display()

                                status_msg = f"✓ 成功保存 {updated_count} 条记录"
                                if errors:
                                    status_msg += f"\n⚠️ {len(errors)} 条记录保存失败:\n" + "\n".join(errors[:3])
                                    if len(errors) > 3:
                                        status_msg += f"\n... 还有 {len(errors)-3} 个错误"

                                return status_msg
                            else:
                                return "⚠️ 没有检测到修改"

                        except Exception as e:
                            import traceback
                            error_detail = traceback.format_exc()
                            return f"✗ 保存失败: {str(e)}\n{error_detail}"

                    # 按ID删除记录
                    def on_delete_by_id(ids_str):
                        """通过ID删除记录"""
                        if not ids_str or not ids_str.strip():
                            return "⚠️ 请输入要删除的记录ID", None, ""

                        try:
                            # 解析ID列表
                            ids = []
                            for id_str in ids_str.split(','):
                                id_str = id_str.strip()
                                if id_str:
                                    try:
                                        ids.append(int(id_str))
                                    except ValueError:
                                        return f"⚠️ 无效的ID: {id_str}", None, ""

                            if not ids:
                                return "⚠️ 未找到有效的记录ID", None, ""

                            # 删除记录
                            success, message, count = self.evaluation_manager.delete_evaluations(ids)

                            if success:
                                df = self.evaluation_manager.get_evaluation_dataframe()
                                dashboard = self._get_dashboard_display()
                                return message, df, dashboard
                            else:
                                return message, None, ""

                        except Exception as e:
                            import traceback
                            error_detail = traceback.format_exc()
                            return f"✗ 删除失败: {str(e)}\n{error_detail}", None, ""

                    # 搜索问题（查看详情）
                    def on_search_question_detail(keyword):
                        results = self.evaluation_manager.search_questions(keyword)
                        if not results:
                            return pd.DataFrame(columns=["问题", "运行次数"]), "⚠️ 未找到匹配的问题", "", ""

                        df = pd.DataFrame([[r['question'], r['count']] for r in results],
                                         columns=["问题", "运行次数"])
                        return df, "✓ 找到 {} 个匹配问题".format(len(results)), "", ""

                    # 查看问题详情
                    def on_view_question_detail(evt: gr.SelectData):
                        """从问题列表中查看详情"""
                        if not evt:
                            return ""

                        selected_question = evt.row[0]  # 获取选中行的问题
                        # 生成问题指纹
                        fingerprint = self.evaluation_manager._generate_fingerprint(selected_question)

                        # 获取该问题的所有运行记录
                        df = self.evaluation_manager.get_question_details(fingerprint)

                        # 计算统计
                        if len(df) > 0:
                            nl2sql_correct = sum(1 for _, row in df.iterrows()
                                               if row['Agent类型'] == 'NL2SQL' and row['是否正确'] == '✓ 正确')
                            nl2sql_total = sum(1 for _, row in df.iterrows()
                                            if row['Agent类型'] == 'NL2SQL')
                            baseline_correct = sum(1 for _, row in df.iterrows()
                                                if row['Agent类型'] == 'Baseline' and row['是否正确'] == '✓ 正确')
                            baseline_total = sum(1 for _, row in df.iterrows()
                                             if row['Agent类型'] == 'Baseline')

                            stats_lines = [
                                f"### 问题统计",
                                f"",
                                f"**问题**：{selected_question}",
                                f"",
                                f"**运行总次数**：{len(df)}",
                                f"",
                                f"**NL2SQL**：{nl2sql_correct}/{nl2sql_total} = {nl2sql_correct/nl2sql_total*100:.1f}%" if nl2sql_total > 0 else "**NL2SQL**：无数据",
                                f"**Baseline**：{baseline_correct}/{baseline_total} = {baseline_correct/baseline_total*100:.1f}%" if baseline_total > 0 else "**Baseline**：无数据"
                            ]
                            stats = "\n".join(stats_lines)
                        else:
                            stats = "⚠️ 无运行记录"

                        return df, stats

                    # 问题Agent筛选
                    def on_question_agent_filter(evt: gr.SelectData, agent_type):
                        """筛选问题的运行记录"""
                        if not evt:
                            return ""

                        selected_question = evt.row[0]
                        fingerprint = self.evaluation_manager._generate_fingerprint(selected_question)

                        if agent_type == "全部":
                            df = self.evaluation_manager.get_question_details(fingerprint)
                        else:
                            df = self.evaluation_manager.get_question_details(fingerprint, agent_type)

                        return df

                    # 绑定事件
                    refresh_eval_btn.click(
                        on_refresh_eval,
                        outputs=[eval_dataframe, dashboard_output]
                    )

                    agent_filter.change(
                        on_agent_filter,
                        inputs=[agent_filter],
                        outputs=[eval_dataframe]
                    )

                    search_question_btn.click(
                        on_search_question,
                        inputs=[question_search_input],
                        outputs=[eval_dataframe]
                    )

                    clear_search_btn.click(
                        on_clear_search,
                        outputs=[eval_dataframe, question_search_input]
                    )

                    # 导出Excel
                    def on_export_excel():
                        return self.evaluation_manager.export_excel()

                    export_csv_btn.click(
                        on_export_eval,
                        outputs=[export_status]
                    )

                    export_excel_btn.click(
                        on_export_excel,
                        outputs=[export_status]
                    )

                    clear_eval_btn.click(
                        on_clear_eval,
                        outputs=[eval_dataframe, dashboard_output]
                    )

                    # 查看问题详情事件
                    search_question_detail_btn.click(
                        on_search_question_detail,
                        inputs=[question_search_detail],
                        outputs=[question_list, question_stats, question_details]
                    )

                    question_list.select(
                        on_view_question_detail,
                        inputs=[question_agent_filter],
                        outputs=[question_details, question_stats]
                    )

                    question_agent_filter.change(
                        on_question_agent_filter,
                        inputs=[gr.State(), question_agent_filter],
                        outputs=[question_details]
                    )

                    # 刷新图表
                    def on_refresh_charts():
                        """刷新失败原因分析图表"""
                        nl2sql_failure_fig = self.evaluation_manager.generate_nl2sql_failure_chart()
                        baseline_failure_fig = self.evaluation_manager.generate_failure_chart()
                        comparison_fig = self.evaluation_manager.generate_comparison_chart()
                        return nl2sql_failure_fig, baseline_failure_fig, comparison_fig

                    refresh_charts_btn.click(
                        on_refresh_charts,
                        outputs=[nl2sql_failure_chart, failure_chart, comparison_chart]
                    )

                    # 保存修改
                    save_changes_btn.click(
                        on_save_changes,
                        inputs=[eval_dataframe],
                        outputs=[save_status]
                    )

                    # 按ID删除
                    delete_by_id_btn.click(
                        on_delete_by_id,
                        inputs=[delete_ids_input],
                        outputs=[delete_status, eval_dataframe, dashboard_output]
                    )

                # Tab 7: 历史会话
                with gr.Tab("📚 历史会话"):
                    gr.Markdown("### 对话历史管理")
                    gr.Markdown("所有对话都会自动保存，可以随时查看历史会话")

                    with gr.Row():
                        with gr.Column(scale=1):
                            refresh_history_btn = gr.Button("刷新列表", variant="secondary", size="sm")

                        history_list_output = gr.Markdown(
                            value=self.get_history_list(),
                            label="历史会话列表"
                        )

                    with gr.Row():
                        with gr.Column(scale=2):
                            # 初始化下拉列表
                            initial_choices = [hf['name'] for hf in self._get_history_files()]

                            history_dropdown = gr.Dropdown(
                                label="选择历史会话",
                                choices=initial_choices,
                                value=initial_choices[0] if initial_choices else None,
                                info="选择要查看或删除的会话"
                            )
                            with gr.Row():
                                load_history_btn = gr.Button("加载会话", variant="primary", scale=1)
                                delete_history_btn = gr.Button("🗑️ 删除会话", variant="stop", scale=1, elem_classes="delete-btn-warning")

                        with gr.Column(scale=3):
                            history_chatbot = gr.Chatbot(
                                label="历史对话内容",
                                height=500
                            )

                    def on_refresh_history():
                        """刷新历史列表和下拉选项"""
                        updated_choices = [hf['name'] for hf in self._get_history_files()]
                        new_list = self.get_history_list()
                        return new_list, gr.Dropdown(choices=updated_choices, value=None)

                    def on_load_history(file_name):
                        """加载选中的历史会话"""
                        if not file_name:
                            return None, "请选择一个历史会话"

                        history = self.load_history(file_name)
                        return history, f"✓ 已加载会话: {file_name}"

                    def on_delete_history(file_name):
                        """删除选中的历史会话"""
                        if not file_name:
                            return gr.Dropdown(), "请选择一个历史会话"

                        success, msg = self.delete_history(file_name)
                        if success:
                            # 刷新列表
                            updated_choices = [hf['name'] for hf in self._get_history_files()]
                            new_list = self.get_history_list()
                            return (
                                gr.Dropdown(choices=updated_choices, value=None),
                                new_list,
                                [],
                                msg
                            )
                        else:
                            return (
                                gr.Dropdown(),
                                self.get_history_list(),
                                None,
                                msg
                            )

                    refresh_history_btn.click(
                        on_refresh_history,
                        outputs=[history_list_output, history_dropdown]
                    )

                    load_history_btn.click(
                        on_load_history,
                        inputs=[history_dropdown],
                        outputs=[history_chatbot, gr.Textbox(label="加载状态", visible=False)]
                    )

                    delete_history_btn.click(
                        on_delete_history,
                        inputs=[history_dropdown],
                        outputs=[history_dropdown, history_list_output, history_chatbot, gr.Textbox(label="删除状态", visible=False)]
                    )

            # 页脚
            gr.Markdown(
                """
                ---
                **注意**: AI 对话功能需要配置 API Key（支持 Google Gemini、OpenAI、Claude 等）

                SQL 执行和数据库结构查看不需要 API Key，可以直接使用
                """
            )

            # 添加自定义CSS样式
            gr.HTML("""
            <style>
            /* 修复英文字符显示样式 */
            .gradio-container {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", Arial, sans-serif !important;
            }

            /* SQL代码块字体 */
            textarea, input[type="text"], .gr-textbox {
                font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace !important;
                font-size: 13px !important;
                line-height: 1.6 !important;
            }

            /* SQL输入框特殊样式 */
            #sql_input {
                font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, "Courier New", monospace !important;
                font-size: 13px !important;
                line-height: 1.6 !important;
                letter-spacing: 0.5px !important;
                white-space: pre !important;
            }

            /* 表格字体 */
            table {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", Arial, sans-serif !important;
            }

            /* 日志输出框字体 */
            #log_output textarea {
                font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, "Courier New", monospace !important;
                font-size: 12px !important;
                line-height: 1.5 !important;
                letter-spacing: 0.5px !important;
                white-space: pre !important;
            }

            /* 对话框字体 */
            .gradio-container .chatbot {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", Arial, sans-serif !important;
            }

            /* 修复英文等宽显示 */
            code, pre, kbd, samp {
                font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace !important;
            }

            /* Markdown内容字体 */
            .gradio-container .markdown-text {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", Arial, sans-serif !important;
            }

            /* DataFrame表格优化 */
            .gradio-container dataframe {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", Arial, sans-serif !important;
            }

            /* 删除按钮警告样式 - 更醒目的红色 */
            .delete-btn-warning {
                background-color: #ef4444 !important;
                color: white !important;
                font-weight: bold !important;
                border: 2px solid #dc2626 !important;
                box-shadow: 0 4px 6px rgba(239, 68, 68, 0.3) !important;
            }
            .delete-btn-warning:hover {
                background-color: #dc2626 !important;
                transform: translateY(-2px);
                box-shadow: 0 6px 12px rgba(239, 68, 68, 0.4) !important;
            }
            .delete-btn-warning:active {
                transform: translateY(0);
                box-shadow: 0 2px 4px rgba(239, 68, 68, 0.2) !important;
            }
            </style>
            """)

        return app


def main():
    """主函数"""
    print("\n" + "="*60)
    print("启动 DbRheo Gradio 应用")
    print("="*60 + "\n")
    
    app = DbRheoWebApp()
    interface = app.create_interface()
    
    print("\n" + "="*60)
    print("[OK] Interface created")
    print("[OK] URL: http://localhost:7860")
    print("[OK] Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    # 启动应用
    interface.launch(
        server_name="127.0.0.1",  # Windows 使用 localhost
        server_port=7860,
        share=False,
        show_error=True,
        quiet=False,
        theme=gr.themes.Soft()
    )


if __name__ == "__main__":
    main()
