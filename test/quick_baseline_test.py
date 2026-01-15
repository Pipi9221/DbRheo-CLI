"""
快速测试脚本 - 测试automotive_questions_list_100.csv的问题
支持自定义测试范围，不依赖标准答案，只记录问题和响应
"""
import sys
import os
import json
import time
import argparse
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
    print(f"❌ 无法导入baseline_agent_enhanced: {e}")
    sys.exit(1)


def load_questions(csv_path: str) -> list:
    """
    加载automotive_questions_list_100.csv文件
    格式：每行一个问题（纯文本，无列名）
    """
    questions = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:  # 跳过空行
                questions.append(line)
    return questions


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='快速测试Baseline Agent - 支持自定义测试范围')
    parser.add_argument('-n', '--num-tests', type=int, default=3,
                       help='测试前N个问题 (默认: 3)')
    parser.add_argument('--start', type=int, default=None,
                       help='从第M个问题开始测试 (从1开始)')
    parser.add_argument('--end', type=int, default=None,
                       help='测试到第N个问题结束')
    parser.add_argument('-q', '--questions-file', type=str, default=None,
                       help='问题文件路径 (默认: question/automotive_questions_list_100.csv)')
    parser.add_argument('--full', action='store_true',
                       help='运行完整测试 (100个问题)')
    return parser.parse_args()


def main():
    """快速测试"""
    # 解析命令行参数
    args = parse_args()

    # 确定测试范围
    if args.full:
        # 完整测试
        NUM_TEST = None  # None 表示全部测试
        START_IDX = 1
    elif args.start is not None or args.end is not None:
        # 自定义范围
        START_IDX = args.start if args.start is not None else 1
        END_IDX = args.end
        NUM_TEST = None
    else:
        # 使用 -n 参数（或默认值）
        NUM_TEST = args.num_tests
        START_IDX = 1
    
    print("\n" + "="*80)
    if args.full:
        print("🚀 快速测试 - 完整测试 (所有问题)")
    elif args.start is not None or args.end is not None:
        range_desc = f"第{START_IDX}个问题"
        if args.end is not None:
            range_desc += f" ~ 第{args.end}个问题"
        print(f"🚀 快速测试 - 自定义范围 ({range_desc})")
    else:
        print(f"🚀 快速测试 - 测试前{NUM_TEST}个问题")
    print("="*80)

    # 配置路径
    baseline_csv = baseline_dir / "数据源_销量.csv"
    questions_csv = Path(__file__).parent / "question" / "automotive_questions_list_100.csv"

    # 支持自定义问题文件路径
    if args.questions_file:
        questions_csv = Path(args.questions_file)

    # 检查文件
    if not baseline_csv.exists():
        print(f"❌ 数据文件不存在: {baseline_csv}")
        return

    if not questions_csv.exists():
        print(f"❌ 问题文件不存在: {questions_csv}")
        return

    # 初始化日志（简化版，直接使用标准logging）
    import logging
    logger = logging.getLogger("quick-baseline-test")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.info(f"快速测试开始")

    # 加载问题
    print(f"\n📂 加载问题文件: {questions_csv}")
    all_questions = load_questions(questions_csv)
    print(f"✅ 总共 {len(all_questions)} 个问题")

    # 应用测试范围
    if args.start is not None or args.end is not None:
        # 自定义范围
        end_idx = args.end if args.end is not None else len(all_questions)
        start_idx = START_IDX - 1  # 转换为0-based索引
        questions = all_questions[start_idx:end_idx]
        print(f"⚠️  自定义范围: 第{START_IDX}个 ~ 第{end_idx}个问题 (共{len(questions)}个)")
    elif args.full:
        # 完整测试
        questions = all_questions
        print(f"⚠️  完整测试模式: 测试所有 {len(questions)} 个问题")
    else:
        # 使用 NUM_TEST
        questions = all_questions[:NUM_TEST]
        print(f"⚠️  快速测试模式: 仅测试前 {len(questions)} 个问题")
    
    # 初始化agent
    print("🤖 初始化Agent...")
    agent = EnhancedBaselineAgent(str(baseline_csv))
    print("✅ Agent初始化成功")
    
    # 准备记录
    test_results = []
    conversation_log = []
    
    # 运行测试
    print(f"\n{'='*80}")
    print(f"📝 开始测试")
    print(f"{'='*80}\n")
    
    start_time = time.time()
    
    for idx, question in enumerate(questions, START_IDX):
        test_id = f"Q{idx}"

        print(f"\n{'='*80}")
        print(f"测试 {idx}/{START_IDX + len(questions) - 1} [{test_id}]")
        print(f"{'='*80}")
        print(f"问题: {question}")
        
        # 记录用户问题
        user_log = {
            "timestamp": datetime.now().isoformat(),
            "role": "user",
            "content": question
        }
        conversation_log.append(user_log)
        
        logger.info(f"开始测试 {test_id}: {question[:50]}")
        
        # 执行查询
        test_start = time.time()
        try:
            result = agent.query(question, verbose=False)
            execution_time = time.time() - test_start
            
            # 记录模型响应
            if result.get("answer"):
                model_log = {
                    "timestamp": datetime.now().isoformat(),
                    "role": "model",
                    "content": result["answer"]
                }
                conversation_log.append(model_log)
            
            # 构建测试结果
            tokens_data = result.get("tokens")
            test_result = {
                "test_num": idx,  # 实际问题编号（从START_IDX开始）
                "test_id": test_id,
                "question": question,
                "success": result["success"],
                "predicted_answer": result.get("answer"),
                "filtered_rows": result.get("filtered_rows", 0),
                "execution_time": round(execution_time, 2),
                "tokens_input": tokens_data.get("prompt") if tokens_data else None,
                "tokens_output": tokens_data.get("completion") if tokens_data else None,
                "tokens_total": tokens_data.get("total") if tokens_data else None,
                "error": result.get("error")
            }
            
            test_results.append(test_result)
            
            # 打印结果摘要
            print(f"\n结果摘要:")
            if result["success"]:
                print(f"  ✅ 查询成功")
                answer = result.get("answer", "")
                print(f"  📊 预测答案: {answer[:100] if answer else 'None'}...")
                print(f"  ⏱️  耗时: {execution_time:.2f}秒")
                logger.info(f"测试 {test_id} 完成 - 成功, 耗时: {execution_time:.2f}秒")
            else:
                print(f"  ❌ 查询失败: {result.get('error', 'Unknown error')}")
                logger.error(f"测试 {test_id} 失败 - 错误: {result.get('error')}")
            
        except Exception as e:
            execution_time = time.time() - test_start
            error_msg = str(e)
            
            # 记录错误响应
            error_log = {
                "timestamp": datetime.now().isoformat(),
                "role": "model",
                "content": f"错误: {error_msg}"
            }
            conversation_log.append(error_log)
            
            test_result = {
                "test_num": idx,  # 实际问题编号（从START_IDX开始）
                "test_id": test_id,
                "question": question,
                "success": False,
                "error": error_msg,
                "execution_time": round(execution_time, 2)
            }
            
            test_results.append(test_result)
            
            print(f"  ❌ 测试失败: {error_msg}")
            logger.error(f"测试 {test_id} 异常 - 错误: {error_msg}")
            import traceback
            traceback.print_exc()
    
    total_time = time.time() - start_time
    
    # 打印总结
    print(f"\n{'='*80}")
    print(f"✅ 测试完成!")
    print(f"{'='*80}")
    print(f"   总耗时: {total_time:.1f}秒")
    print(f"   平均: {total_time/len(questions):.2f}秒/题")
    
    # 保存结果
    result_dir = Path(__file__).parent / "result"
    result_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. 保存对话日志（JSONL）
    log_file = result_dir / f"quick_test_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, 'w', encoding='utf-8') as f:
        for log_entry in conversation_log:
            json.dump(log_entry, f, ensure_ascii=False)
            f.write('\n')
    print(f"\n💾 对话日志: {log_file}")
    
    # 2. 保存测试结果（JSON）
    results_file = result_dir / f"quick_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
    print(f"💾 测试结果: {results_file}")
    
    # 统计
    successful_tests = sum(1 for r in test_results if r['success'])
    print(f"\n📊 测试摘要:")
    print(f"   总测试数: {len(test_results)}")
    print(f"   成功查询: {successful_tests} ({successful_tests/len(test_results)*100:.1f}%)")
    
    print(f"\n{'='*80}")
    print("✅ 快速测试完成！")
    print(f"📝 使用示例:")
    print(f"   python quick_baseline_test.py --start 11 --end 15  # 测试第11-15个问题")
    print(f"   python quick_baseline_test.py -n 10                 # 测试前10个问题")
    print(f"   python quick_baseline_test.py --full                # 测试所有问题")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
