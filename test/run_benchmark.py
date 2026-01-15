"""
Benchmark测试脚本 - 批量测试baseline_agent_enhanced.py
测试结果保存到CSV和JSON格式
"""
import sys
import os
import csv
import json
import time
import re
from datetime import datetime
from pathlib import Path
import pandas as pd

# 添加项目路径
project_root = Path(__file__).parent.parent
baseline_dir = project_root / "baseline"
sys.path.insert(0, str(baseline_dir))

# 导入agent
from baseline_agent_enhanced import EnhancedBaselineAgent

class BenchmarkTester:
    """Benchmark测试器"""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.agent = None
        self.results = []
        
    def initialize_agent(self):
        """初始化agent"""
        print(f"\n{'='*80}")
        print(f"🚀 初始化Agent...")
        print(f"{'='*80}")
        self.agent = EnhancedBaselineAgent(self.csv_path)
        
    def load_benchmark_questions(self, benchmark_csv: str) -> pd.DataFrame:
        """加载benchmark问题"""
        print(f"\n📂 加载benchmark问题: {benchmark_csv}")
        df = pd.read_csv(benchmark_csv)
        print(f"✅ 加载 {len(df)} 个问题")
        print(f"   问题类型分布: {df['Type'].value_counts().to_dict()}")
        return df
    
    def extract_answer_number(self, answer: str) -> float:
        """
        从答案中提取数字
        新格式：【答案：具体数值】
        旧格式：result = xxx（兼容）
        """
        if pd.isna(answer) or answer is None:
            return None

        answer = str(answer).strip()

        # 优先提取新格式：【答案：xxx】
        new_match = re.search(r'【答案：\s*([+-]?\d+\.?\d*)', answer)
        if new_match:
            value_str = new_match.group(1)
            # 处理null
            if value_str.lower() == 'null':
                return None
            return float(value_str)

        # 兼容旧格式：result = xxx
        result_match = re.search(r'result\s*=\s*([+-]?\d+\.?\d*)', answer, re.IGNORECASE)
        if result_match:
            value_str = result_match.group(1)
            # 处理null
            if value_str.lower() == 'null':
                return None
            return float(value_str)

        # 如果没有找到任何格式，尝试提取null
        if '【答案：null】' in answer or '【答案： null】' in answer or 'null' in answer.lower() or '无' in answer or '不适用' in answer:
            return None

        # 降级方案：提取所有数字
        numbers = re.findall(r'-?\d+\.?\d*', answer)
        if numbers:
            # 过滤掉年份（1000-2100），取最大值
            num_values = [float(n) for n in numbers]
            filtered_nums = [n for n in num_values if not (1000 <= n <= 2100)]
            if filtered_nums:
                return max(filtered_nums)
            return max(num_values) if num_values else None

        return None
    
    def compare_results(self, predicted: str, expected: str, tolerance: float = 0.01) -> dict:
        """
        比较预测结果和期望结果
        :param predicted: 预测答案
        :param expected: 期望答案
        :param tolerance: 容差（百分比）
        :return: 比较结果字典
        """
        comparison = {
            "match": False,
            "predicted_number": None,
            "expected_number": None,
            "difference": None,
            "difference_percent": None,
            "within_tolerance": False
        }
        
        # 提取数字
        pred_num = self.extract_answer_number(predicted)
        
        # 期望答案通常是"数字 单位"格式，简单提取第一个数字
        if pd.isna(expected) or expected is None:
            exp_num = None
        else:
            # 提取期望答案中的数字（如 "4045 辆" -> 4045）
            exp_match = re.search(r'([+-]?\d+\.?\d*)', str(expected))
            if exp_match:
                exp_num = float(exp_match.group(1))
            else:
                exp_num = None
        
        comparison["predicted_number"] = pred_num
        comparison["expected_number"] = exp_num
        
        # 如果任一数字为None，无法比较
        if pred_num is None or exp_num is None:
            comparison["match"] = False
            return comparison
        
        # 计算差异
        difference = abs(pred_num - exp_num)
        comparison["difference"] = difference
        
        # 计算百分比差异
        if exp_num != 0:
            difference_percent = (difference / abs(exp_num)) * 100
            comparison["difference_percent"] = difference_percent
            comparison["within_tolerance"] = difference_percent <= tolerance
        else:
            comparison["difference_percent"] = None
            comparison["within_tolerance"] = difference <= tolerance
        
        # 判断是否匹配（在容差范围内）
        comparison["match"] = comparison["within_tolerance"]
        
        return comparison
    
    def run_single_test(self, row: pd.Series, test_num: int, total_tests: int) -> dict:
        """运行单个测试"""
        question_id = f"Q{test_num}"
        question_type = row['Type']
        question_text = row['Question']
        expected_sql = row['SQL']
        expected_answer = row['Answer']
        
        print(f"\n{'='*80}")
        print(f"📝 测试 {test_num}/{total_tests} [{question_id}] - Type {question_type}")
        print(f"{'='*80}")
        print(f"问题: {question_text}")
        print(f"期望答案: {expected_answer}")
        
        # 执行查询（verbose=False，减少输出）
        start_time = time.time()
        result = self.agent.query(question_text, verbose=False)
        execution_time = time.time() - start_time
        
        # 添加基础信息
        test_result = {
            "test_num": test_num,
            "test_id": question_id,
            "type": question_type,
            "question": question_text,
            "expected_sql": expected_sql,
            "expected_answer": expected_answer,
            "execution_time": round(execution_time, 2),
            "timestamp": datetime.now().isoformat()
        }
        
        # 添加agent结果
        test_result.update({
            "success": result["success"],
            "predicted_answer": result["answer"],
            "filtered_rows": result["filtered_rows"],
            "error": result.get("error"),
            "tokens_input": result.get("tokens", {}).get("prompt") if result.get("tokens") else None,
            "tokens_output": result.get("tokens", {}).get("completion") if result.get("tokens") else None,
            "tokens_total": result.get("tokens", {}).get("total") if result.get("tokens") else None,
            "llm_duration_ms": result.get("duration_ms")
        })
        
        # 比较结果
        if result["success"] and result["answer"]:
            comparison = self.compare_results(result["answer"], expected_answer)
            test_result.update(comparison)
        
        # 打印结果摘要
        print(f"\n结果摘要:")
        if test_result["success"]:
            print(f"  ✅ 查询成功")
            print(f"  📊 预测答案: {result['answer'][:100]}...")
            if "match" in test_result:
                print(f"  🎯 匹配结果: {'✅ 匹配' if test_result['match'] else '❌ 不匹配'}")
                if test_result["difference_percent"] is not None:
                    print(f"  📉 差异: {test_result['difference_percent']:.2f}%")
            print(f"  ⏱️ 耗时: {execution_time:.2f}秒")
        else:
            print(f"  ❌ 查询失败: {test_result.get('error', 'Unknown error')}")
        
        return test_result
    
    def run_benchmark(self, benchmark_csv: str, output_dir: str = None, max_tests: int = None, start_idx: int = 1):
        """
        运行完整benchmark测试
        :param benchmark_csv: benchmark CSV文件路径
        :param output_dir: 输出目录
        :param max_tests: 最大测试数量（None表示全部测试）
        :param start_idx: 起始测试索引（从1开始）
        """
        print(f"\n{'='*80}")
        print(f"🚀 开始Benchmark测试")
        print(f"{'='*80}")

        # 初始化agent
        self.initialize_agent()

        # 加载问题
        df = self.load_benchmark_questions(benchmark_csv)

        # 应用起始索引
        if start_idx > 1:
            # Python 使用 0-based 索引，所以 start_idx-1
            df = df.iloc[start_idx - 1:].copy()
            df.index = range(1, len(df) + 1)  # 重置索引从1开始
            print(f"\n⚠️  起始索引: 第{start_idx}个问题")

        # 限制测试数量
        if max_tests and max_tests < len(df):
            df = df.head(max_tests)
            print(f"⚠️  限制测试数量: {max_tests}")

        total_tests = len(df)
        print(f"\n📊 计划测试 {total_tests} 个问题")
        print(f"   测试范围: 第{start_idx}个 ~ 第{start_idx + total_tests - 1}个问题")

        # 运行测试
        start_time = time.time()
        self.results = []

        for idx, row in df.iterrows():
            test_num = start_idx + idx  # 计算实际测试编号
            try:
                test_result = self.run_single_test(row, test_num, total_tests)
                self.results.append(test_result)

                # 每10个测试显示进度
                if test_num % 10 == 0:
                    elapsed = time.time() - start_time
                    avg_time = elapsed / (test_num - start_idx + 1)
                    print(f"\n📈 进度: {test_num}/{start_idx + total_tests - 1} ({(test_num - start_idx + 1)/total_tests*100:.1f}%)")
                    print(f"   已用时间: {elapsed:.1f}秒")
                    print(f"   平均耗时: {avg_time:.2f}秒/题")
                    print(f"   预计剩余: {avg_time * (total_tests - (test_num - start_idx + 1)):.1f}秒")

            except Exception as e:
                print(f"\n❌ 测试 {test_num} 失败: {str(e)}")
                import traceback
                traceback.print_exc()
                # 添加失败记录
                self.results.append({
                    "test_num": test_num,
                    "test_id": f"Q{test_num}",
                    "type": row.get('Type'),
                    "question": row.get('Question'),
                    "expected_answer": row.get('Answer'),
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })

        total_time = time.time() - start_time
        print(f"\n{'='*80}")
        print(f"✅ 测试完成!")
        print(f"{'='*80}")
        print(f"   总耗时: {total_time:.1f}秒")
        print(f"   平均: {total_time/len(self.results):.2f}秒/题")

        # 保存结果
        if output_dir is None:
            output_dir = str(Path(__file__).parent / "result")

        self.save_results(output_dir)
        self.generate_summary(output_dir)
    
    def save_results(self, output_dir: str):
        """保存测试结果到文件"""
        print(f"\n💾 保存结果到: {output_dir}")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 保存为JSON
        json_file = output_path / "benchmark_results.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        print(f"  ✅ JSON: {json_file}")
        
        # 保存为CSV
        csv_file = output_path / "benchmark_results.csv"
        pd.DataFrame(self.results).to_csv(csv_file, index=False, encoding='utf-8-sig')
        print(f"  ✅ CSV: {csv_file}")
        
        # 保存详细日志
        log_file = output_path / "benchmark_detailed.log"
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("Benchmark测试详细日志\n")
            f.write("="*80 + "\n\n")
            
            for result in self.results:
                f.write(f"测试 {result['test_num']} [{result['test_id']}]\n")
                f.write("-"*80 + "\n")
                f.write(f"类型: {result['type']}\n")
                f.write(f"问题: {result['question']}\n")
                f.write(f"期望答案: {result['expected_answer']}\n")
                f.write(f"预测答案: {result['predicted_answer']}\n")
                f.write(f"成功: {'✅' if result['success'] else '❌'}\n")
                
                if 'match' in result:
                    f.write(f"匹配: {'✅' if result['match'] else '❌'}\n")
                    if result['difference_percent'] is not None:
                        f.write(f"差异: {result['difference_percent']:.2f}%\n")
                
                if result['error']:
                    f.write(f"错误: {result['error']}\n")
                
                f.write(f"耗时: {result['execution_time']}秒\n")
                f.write(f"时间戳: {result['timestamp']}\n\n")
        
        print(f"  ✅ 日志: {log_file}")
    
    def generate_summary(self, output_dir: str):
        """生成测试摘要报告"""
        print(f"\n📊 生成摘要报告...")
        
        # 统计数据
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r['success'])
        matched_tests = sum(1 for r in self.results if r.get('match', False))
        
        # 类型统计
        type_stats = {}
        for result in self.results:
            t = result['type']
            if t not in type_stats:
                type_stats[t] = {'total': 0, 'success': 0, 'match': 0}
            type_stats[t]['total'] += 1
            if result['success']:
                type_stats[t]['success'] += 1
            if result.get('match', False):
                type_stats[t]['match'] += 1
        
        # Token统计
        total_tokens = sum(r.get('tokens_total', 0) for r in self.results)
        avg_tokens = total_tokens / total_tests if total_tests > 0 else 0
        
        # 耗时统计
        total_time = sum(r['execution_time'] for r in self.results)
        avg_time = total_time / total_tests if total_tests > 0 else 0
        
        # 生成摘要
        summary = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": f"{successful_tests/total_tests*100:.2f}%",
            "matched_tests": matched_tests,
            "match_rate": f"{matched_tests/total_tests*100:.2f}%" if total_tests > 0 else "N/A",
            "total_tokens": total_tokens,
            "avg_tokens": f"{avg_tokens:.0f}",
            "total_time": f"{total_time:.1f}s",
            "avg_time": f"{avg_time:.2f}s",
            "type_stats": type_stats,
            "generated_at": datetime.now().isoformat()
        }
        
        # 保存摘要
        summary_file = Path(output_dir) / "benchmark_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        # 生成Markdown报告
        md_file = Path(output_dir) / "benchmark_report.md"
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write("# Benchmark测试报告\n\n")
            f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## 总体统计\n\n")
            f.write(f"| 指标 | 数值 |\n")
            f.write(f"|------|------|\n")
            f.write(f"| 总测试数 | {total_tests} |\n")
            f.write(f"| 成功查询 | {successful_tests} ({successful_tests/total_tests*100:.2f}%) |\n")
            f.write(f"| 匹配答案 | {matched_tests} ({matched_tests/total_tests*100:.2f}%) |\n")
            f.write(f"| 总Token消耗 | {total_tokens:,} |\n")
            f.write(f"| 平均Token/题 | {avg_tokens:.0f} |\n")
            f.write(f"| 总耗时 | {total_time:.1f}秒 |\n")
            f.write(f"| 平均耗时/题 | {avg_time:.2f}秒 |\n\n")
            
            f.write("## 类型统计\n\n")
            f.write(f"| 类型 | 总数 | 成功 | 匹配 | 成功率 | 匹配率 |\n")
            f.write(f"|------|------|------|------|--------|--------|\n")
            for t, stats in sorted(type_stats.items()):
                success_rate = f"{stats['success']/stats['total']*100:.1f}%" if stats['total'] > 0 else "N/A"
                match_rate = f"{stats['match']/stats['total']*100:.1f}%" if stats['total'] > 0 else "N/A"
                f.write(f"| {t} | {stats['total']} | {stats['success']} | {stats['match']} | {success_rate} | {match_rate} |\n")
            
            f.write("\n## 详细结果\n\n")
            f.write("请查看 `benchmark_results.csv` 或 `benchmark_results.json` 获取详细结果。\n")
        
        print(f"  ✅ 摘要: {summary_file}")
        print(f"  ✅ 报告: {md_file}")
        
        # 打印摘要
        print(f"\n{'='*80}")
        print(f"📊 测试摘要")
        print(f"{'='*80}")
        print(f"   总测试数: {total_tests}")
        print(f"   成功查询: {successful_tests} ({successful_tests/total_tests*100:.2f}%)")
        print(f"   匹配答案: {matched_tests} ({matched_tests/total_tests*100:.2f}%)")
        print(f"   总Token: {total_tokens:,} (平均 {avg_tokens:.0f}/题)")
        print(f"   总耗时: {total_time:.1f}秒 (平均 {avg_time:.2f}秒/题)")
        print(f"{'='*80}\n")


def main():
    """主函数"""
    # 配置路径
    baseline_dir = Path(__file__).parent.parent / "baseline"
    csv_path = baseline_dir / "数据源_销量.csv"
    benchmark_csv = Path(__file__).parent / "question" / "benchmark_100_questions_final.csv"
    
    # 检查文件
    if not csv_path.exists():
        print(f"❌ CSV文件不存在: {csv_path}")
        return
    
    if not benchmark_csv.exists():
        print(f"❌ Benchmark文件不存在: {benchmark_csv}")
        return
    
    # 创建测试器
    tester = BenchmarkTester(str(csv_path))
    
    # 询问是否限制测试数量
    print(f"\n📋 配置:")
    print(f"   数据源: {csv_path}")
    print(f"   测试集: {benchmark_csv}")
    print(f"\n是否限制测试数量？")
    print(f"  - 输入数字: 测试前N个问题")
    print(f"  - 直接回车: 测试全部问题")
    
    max_tests = input("\n请选择: ").strip()
    max_tests = int(max_tests) if max_tests.isdigit() else None
    
    # 运行benchmark
    tester.run_benchmark(
        benchmark_csv=str(benchmark_csv),
        max_tests=max_tests
    )


if __name__ == "__main__":
    main()
