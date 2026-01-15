"""
快速测试脚本 - 支持自定义测试数量
"""
import sys
import argparse
from pathlib import Path

# 添加路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "test"))

from run_benchmark import BenchmarkTester


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='快速测试Baseline Agent - 支持自定义测试范围',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 快速测试（默认前3个问题）
  python quick_test_benchmark.py

  # 测试前10个问题
  python quick_test_benchmark.py -n 10

  # 测试第5到第15个问题（区间测试）
  python quick_test_benchmark.py --start 5 --end 15

  # 测试第20到第30个问题
  python quick_test_benchmark.py --start 20 --end 30

  # 测试从第50个开始的所有问题
  python quick_test_benchmark.py --start 50

  # 指定问题文件并测试区间
  python quick_test_benchmark.py -q question/automotive_questions_list_100.csv --start 10 --end 20
        """
    )

    parser.add_argument(
        '-n', '--num-tests',
        type=int,
        default=3,
        metavar='N',
        help='测试前N个问题 (默认: 3)'
    )

    parser.add_argument(
        '--start',
        type=int,
        default=None,
        metavar='M',
        help='从第M个问题开始测试 (从1开始)'
    )

    parser.add_argument(
        '--end',
        type=int,
        default=None,
        metavar='N',
        help='测试到第N个问题结束'
    )

    parser.add_argument(
        '-q', '--questions-file',
        type=str,
        default=None,
        metavar='FILE',
        help='问题文件路径 (默认: question/benchmark_100_questions_final.csv)'
    )

    parser.add_argument(
        '--full',
        action='store_true',
        help='运行完整测试（测试所有问题）'
    )

    return parser.parse_args()


def main():
    """快速测试"""
    args = parse_args()

    print("\n" + "="*80)
    print("🚀 快速测试 - Baseline Agent测试")
    print("="*80)

    # 配置路径
    baseline_dir = project_root / "baseline"
    csv_path = baseline_dir / "数据源_销量.csv"

    # 确定问题文件
    if args.questions_file:
        benchmark_csv = Path(args.questions_file)
    else:
        benchmark_csv = Path(__file__).parent / "question" / "benchmark_100_questions_final.csv"

    # 确定测试范围
    if args.full:
        # 完整测试
        max_tests = None
        print(f"📋 模式: 完整测试（所有问题）")
    elif args.start is not None or args.end is not None:
        # 区间测试
        start_idx = args.start if args.start is not None else 1
        end_idx = args.end if args.end is not None else None

        if args.start and args.end:
            # 同时指定了 start 和 end，测试 [start, end] 区间
            print(f"📋 模式: 区间测试（第{start_idx}到第{end_idx}个问题）")
            max_tests = end_idx  # 限制到end
        elif args.start:
            # 只指定了 start，从 start 开始到结束
            print(f"📋 模式: 从第{start_idx}个问题开始测试")
            max_tests = None  # 不限制
        else:
            # 只指定了 end，测试前 end 个
            print(f"📋 模式: 测试前{end_idx}个问题")
            max_tests = end_idx
    else:
        # 使用 -n 参数
        num_tests = args.num_tests
        start_idx = 1
        max_tests = num_tests if num_tests > 0 else None
        if num_tests > 0:
            print(f"📋 模式: 测试前{num_tests}个问题")
        else:
            print(f"📋 模式: 完整测试")

    # 检查参数有效性
    if args.start is not None and args.end is not None:
        if args.start > args.end:
            print(f"❌ 错误: 起始索引 ({args.start}) 不能大于结束索引 ({args.end})")
            return

    if args.start is not None and args.start < 1:
        print(f"❌ 错误: 起始索引必须 >= 1")
        return

    # 检查文件
    if not csv_path.exists():
        print(f"❌ CSV文件不存在: {csv_path}")
        return

    if not benchmark_csv.exists():
        print(f"❌ 问题文件不存在: {benchmark_csv}")
        return

    # 创建测试器
    tester = BenchmarkTester(str(csv_path))

    # 运行测试
    print(f"\n📁 数据源: {csv_path}")
    print(f"📁 问题文件: {benchmark_csv}")
    print(f"🔢 测试范围: 第{start_idx}个问题 ~ {f'第{max_tests}个问题' if max_tests else '最后'}")
    print()

    tester.run_benchmark(
        benchmark_csv=str(benchmark_csv),
        max_tests=max_tests,
        start_idx=start_idx
    )

    print("\n✅ 测试完成！")
    if args.start and args.end:
        print(f"📊 已测试第{args.start}到第{args.end}个问题")
    elif args.start:
        print(f"📊 已测试从第{args.start}个问题开始")
    elif args.end:
        print(f"📊 已测试前{args.end}个问题")
    elif max_tests:
        print(f"📊 已测试{max_tests}个问题")
    print("📝 查看结果文件:")
    print("   test/result/benchmark_results.json")
    print("   test/result/benchmark_results.csv")
    print("   test/result/benchmark_detailed.log")


if __name__ == "__main__":
    main()
