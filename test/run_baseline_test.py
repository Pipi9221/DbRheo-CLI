"""
Baseline测试脚本 - 集成日志系统
- 引入packages包下的日志系统
- 读取测试集CSV文件
- 记录问题和LLM输出结果（JSONL格式）
- 最终将日志持久化到result/baseline.json
"""
import sys
import os
import csv
import json
import time
from datetime import datetime
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
baseline_dir = project_root / "baseline"
packages_dir = project_root / "packages" / "core" / "src"

sys.path.insert(0, str(baseline_dir))
sys.path.insert(0, str(packages_dir))

# 导入agent
try:
    from baseline_agent_enhanced import EnhancedBaselineAgent
except ImportError as e:
    print(f"警告: 无法导入baseline_agent_enhanced: {e}")
    print("将使用简化的测试模式...")
    EnhancedBaselineAgent = None

# 导入日志系统
try:
    from dbrheo.telemetry.logger import DatabaseLogger
    from dbrheo.config.base import DatabaseConfig
    HAS_LOGGER = True
except ImportError as e:
    print(f"警告: 无法导入日志系统: {e}")
    print("将使用基础日志...")
    HAS_LOGGER = False
    DatabaseLogger = None
    DatabaseConfig = None

# 尝试导入pandas
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    print("警告: 无法导入pandas，将使用基础CSV读取")
    HAS_PANDAS = False
    pd = None


class BaselineTester:
    """Baseline测试器 - 集成日志系统"""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.agent = None
        self.conversation_log = []  # 存储对话日志
        self.logger = None
        
        # 初始化日志系统
        self._init_logger()
    
    def _init_logger(self):
        """初始化日志系统"""
        if HAS_LOGGER and DatabaseLogger and DatabaseConfig:
            try:
                # 创建基础配置
                config = DatabaseConfig({
                    "service_name": "baseline-test",
                    "log_level": "INFO",
                    "log_format": "text"
                })
                
                self.logger = DatabaseLogger(config)
                self.logger.info("Baseline测试器初始化", csv_path=self.csv_path)
            except Exception as e:
                print(f"警告: 初始化日志系统失败: {e}")
                self.logger = None
        else:
            # 使用简单的打印日志
            print(f"[INFO] Baseline测试器初始化: {self.csv_path}")
    
    def _log(self, level: str, message: str, **kwargs):
        """统一日志记录接口"""
        if self.logger:
            if level == "info":
                self.logger.info(message, **kwargs)
            elif level == "error":
                self.logger.error(message, **kwargs)
            elif level == "warning":
                self.logger.warning(message, **kwargs)
        else:
            prefix = f"[{level.upper()}]"
            if kwargs:
                print(f"{prefix} {message} {kwargs}")
            else:
                print(f"{prefix} {message}")
    
    def initialize_agent(self):
        """初始化agent"""
        self._log("info", "初始化Agent...")
        
        if not EnhancedBaselineAgent:
            raise RuntimeError("baseline_agent_enhanced 未成功导入，无法初始化Agent")
        
        self.agent = EnhancedBaselineAgent(self.csv_path)
        
        self._log("info", "Agent初始化成功",
                 model=self.agent.model,
                 data_rows=len(self.agent.df))
    
    def load_questions(self, csv_path: str) -> list:
        """
        加载测试问题
        读取CSV文件，每行是一个问题（可能有空行分隔）
        """
        self._log("info", f"加载测试问题: {csv_path}")
        
        questions = []
        
        # 先尝试作为文本文件读取（处理空行分隔的情况）
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:  # 跳过空行
                        questions.append(line)
        except Exception as e:
            # 如果文本读取失败，尝试作为CSV读取
            if HAS_PANDAS:
                df = pd.read_csv(csv_path)
                
                # 提取问题列表（假设第一列是问题，列名可能是"Question"或其他）
                if 'Question' in df.columns:
                    questions = df['Question'].dropna().tolist()
                elif 'question' in df.columns:
                    questions = df['question'].dropna().tolist()
                else:
                    # 如果没有明确的列名，使用第一列
                    questions = df.iloc[:, 0].dropna().tolist()
            else:
                # 使用基础CSV读取
                questions = []
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if row:  # 跳过空行
                            questions.append(row[0])  # 取第一列
        
        self._log("info", f"加载了 {len(questions)} 个问题")
        return questions
    
    def _log_interaction(self, role: str, content: str):
        """
        记录单次交互
        格式: {"timestamp": "2026-01-13T16:32:35.833746", "role": "user/model", "content": "..."}
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content
        }
        self.conversation_log.append(log_entry)
        return log_entry
    
    def run_single_test(self, question: str, test_num: int, total_tests: int) -> dict:
        """
        运行单个测试并记录日志
        """
        test_id = f"Q{test_num}"
        
        print(f"\n{'='*80}")
        print(f"📝 测试 {test_num}/{total_tests} [{test_id}]")
        print(f"{'='*80}")
        print(f"问题: {question}")
        
        # 记录用户问题
        self._log_interaction("user", question)
        self._log("info", f"开始测试 {test_id}", question=question[:50])
        
        # 执行查询
        start_time = time.time()
        try:
            result = self.agent.query(question, verbose=False)
            execution_time = time.time() - start_time
            
            # 记录模型响应
            answer = result.get("answer", "")
            if answer:
                self._log_interaction("model", answer)
            
            # 构建测试结果
            test_result = {
                "test_num": test_num,
                "test_id": test_id,
                "question": question,
                "success": result["success"],
                "predicted_answer": result["answer"],
                "filtered_rows": result.get("filtered_rows", 0),
                "execution_time": round(execution_time, 2),
                "tokens_input": result.get("tokens", {}).get("prompt"),
                "tokens_output": result.get("tokens", {}).get("completion"),
                "tokens_total": result.get("tokens", {}).get("total"),
                "error": result.get("error")
            }
            
            # 打印结果摘要
            print(f"\n结果摘要:")
            if test_result["success"]:
                print(f"  ✅ 查询成功")
                print(f"  📊 预测答案: {answer[:100] if answer else 'None'}...")
                print(f"  ⏱️ 耗时: {execution_time:.2f}秒")
                self._log("info", f"测试 {test_id} 完成",
                         success=True,
                         execution_time=execution_time)
            else:
                print(f"  ❌ 查询失败: {test_result.get('error', 'Unknown error')}")
                self._log("error", f"测试 {test_id} 失败",
                         error=test_result.get('error'))
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            # 记录错误响应
            self._log_interaction("model", f"错误: {error_msg}")
            
            test_result = {
                "test_num": test_num,
                "test_id": test_id,
                "question": question,
                "success": False,
                "error": error_msg,
                "execution_time": round(execution_time, 2)
            }
            
            print(f"  ❌ 测试失败: {error_msg}")
            self._log("error", f"测试 {test_id} 异常", error=error_msg)
            import traceback
            traceback.print_exc()
        
        return test_result
    
    def run_tests(self, questions_csv: str, output_dir: str = None):
        """
        运行批量测试
        :param questions_csv: 测试问题CSV文件路径
        :param output_dir: 输出目录
        """
        print(f"\n{'='*80}")
        print(f"🚀 开始Baseline测试")
        print(f"{'='*80}")
        
        # 初始化agent
        self.initialize_agent()
        
        # 加载问题
        questions = self.load_questions(questions_csv)
        total_tests = len(questions)
        
        print(f"\n📊 计划测试 {total_tests} 个问题")
        
        # 运行测试
        start_time = time.time()
        test_results = []
        
        for idx, question in enumerate(questions, 1):
            test_result = self.run_single_test(question, idx, total_tests)
            test_results.append(test_result)
            
            # 每10个测试显示进度
            if idx % 10 == 0:
                elapsed = time.time() - start_time
                avg_time = elapsed / idx
                print(f"\n📈 进度: {idx}/{total_tests} ({idx/total_tests*100:.1f}%)")
                print(f"   已用时间: {elapsed:.1f}秒")
                print(f"   平均耗时: {avg_time:.2f}秒/题")
                print(f"   预计剩余: {avg_time * (total_tests - idx):.1f}秒")
                self._log("info", f"进度更新",
                         completed=idx,
                         total=total_tests,
                         avg_time=f"{avg_time:.2f}s")
        
        total_time = time.time() - start_time
        print(f"\n{'='*80}")
        print(f"✅ 测试完成!")
        print(f"{'='*80}")
        print(f"   总耗时: {total_time:.1f}秒")
        print(f"   平均: {total_time/total_tests:.2f}秒/题")
        
        self._log("info", "所有测试完成",
                total_tests=total_tests,
                total_time=f"{total_time:.1f}s",
                avg_time=f"{total_time/total_tests:.2f}s")
        
        # 保存结果
        if output_dir is None:
            output_dir = str(Path(__file__).parent / "result")
        
        self.save_results(output_dir, test_results)
    
    def save_results(self, output_dir: str, test_results: list):
        """
        保存测试结果和对话日志
        :param output_dir: 输出目录
        :param test_results: 测试结果列表
        """
        print(f"\n💾 保存结果到: {output_dir}")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 生成时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 1. 保存对话日志（JSONL格式）- baseline_log_{timestamp}.json
        baseline_log_file = output_path / f"baseline_log_{timestamp}.json"
        with open(baseline_log_file, 'w', encoding='utf-8') as f:
            for log_entry in self.conversation_log:
                json.dump(log_entry, f, ensure_ascii=False)
                f.write('\n')
        print(f"  ✅ 对话日志: {baseline_log_file}")
        self._log("info", f"对话日志已保存", path=str(baseline_log_file),
                 entries=len(self.conversation_log))

        # 2. 保存测试结果（JSON格式）
        results_file = output_path / f"baseline_results_{timestamp}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, ensure_ascii=False, indent=2)
        print(f"  ✅ 测试结果: {results_file}")
        self._log("info", f"测试结果已保存", path=str(results_file))

        # 3. 生成摘要报告
        self.generate_summary(output_path, test_results)
    
    def generate_summary(self, output_path: Path, test_results: list):
        """生成测试摘要报告"""
        print(f"\n📊 生成摘要报告...")

        # 统计数据
        total_tests = len(test_results)
        successful_tests = sum(1 for r in test_results if r['success'])

        # Token统计
        total_tokens = sum(r.get('tokens_total', 0) for r in test_results)
        avg_tokens = total_tokens / total_tests if total_tests > 0 else 0

        # 耗时统计
        total_time = sum(r['execution_time'] for r in test_results)
        avg_time = total_time / total_tests if total_tests > 0 else 0

        # 生成摘要
        summary = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": f"{successful_tests/total_tests*100:.2f}%" if total_tests > 0 else "N/A",
            "total_tokens": total_tokens,
            "avg_tokens": f"{avg_tokens:.0f}" if avg_tokens > 0 else "N/A",
            "total_time": f"{total_time:.1f}s",
            "avg_time": f"{avg_time:.2f}s",
            "generated_at": datetime.now().isoformat()
        }

        # 保存摘要（带时间戳）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        summary_file = output_path / f"baseline_summary_{timestamp}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"  ✅ 摘要: {summary_file}")
        
        # 打印摘要
        print(f"\n{'='*80}")
        print(f"📊 测试摘要")
        print(f"{'='*80}")
        print(f"   总测试数: {total_tests}")
        print(f"   成功查询: {successful_tests} ({successful_tests/total_tests*100:.2f}%)")
        print(f"   总Token: {total_tokens:,} (平均 {avg_tokens:.0f}/题)")
        print(f"   总耗时: {total_time:.1f}秒 (平均 {avg_time:.2f}秒/题)")
        print(f"{'='*80}\n")
        
        self._log("info", "摘要报告生成完成", summary=summary)


def main():
    """主函数"""
    # 配置路径
    baseline_dir = Path(__file__).parent.parent / "baseline"
    csv_path = baseline_dir / "数据源_销量.csv"
    questions_csv = Path(__file__).parent / "question" / "automotive_questions_list_100.csv"
    
    # 检查文件
    if not csv_path.exists():
        print(f"❌ CSV文件不存在: {csv_path}")
        return
    
    if not questions_csv.exists():
        print(f"❌ 测试问题文件不存在: {questions_csv}")
        return
    
    # 创建测试器
    tester = BaselineTester(str(csv_path))
    
    # 运行测试
    tester.run_tests(str(questions_csv))


if __name__ == "__main__":
    main()
