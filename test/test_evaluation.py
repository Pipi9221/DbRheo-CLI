"""
测试 EvaluationManager 功能
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from gradio_app import EvaluationManager

def test_evaluation_manager():
    """测试评估管理器"""
    print("="*60)
    print("测试 EvaluationManager")
    print("="*60 + "\n")

    # 创建评估管理器
    eval_mgr = EvaluationManager()

    # 测试答案提取
    print("1. 测试答案提取:")
    test_responses = [
        "根据查询结果，【答案：-11.56%】",
        "【答案: 12345】",
        "答案：2023年12月，比亚迪的销量为15000辆",
        "Answer: The sales volume is 50000",
        "没有标准格式的答案"
    ]

    for response in test_responses:
        extracted = eval_mgr.extract_answer(response)
        print(f"  响应: {response[:50]}...")
        print(f"  提取: {extracted}")
        print()

    # 测试答案比较
    print("2. 测试答案比较:")
    test_cases = [
        ("-11.56%", "-11.56%"),
        ("-11.56%", "-11.50%"),
        ("10000", "10000"),
        ("10000", "10500"),
        ("比亚迪", "比亚迪汽车的销量很高"),
        ("测试", "完全不同的答案")
    ]

    for std, act in test_cases:
        is_correct, reason = eval_mgr.compare_answers(std, act)
        status = "✓ 正确" if is_correct else "✗ 错误"
        print(f"  标准: {std} | 实际: {act}")
        print(f"  结果: {status} - {reason}")
        print()

    # 测试添加评估记录
    print("3. 测试添加评估记录:")
    eval_mgr.add_evaluation(
        question="2023-12，一汽大众的销量是多少？",
        standard_answer="15000",
        actual_response="根据查询结果，【答案：15000】",
        agent_type="NL2SQL"
    )

    eval_mgr.add_evaluation(
        question="2023年比亚迪的总销量是多少？",
        standard_answer="100000",
        actual_response="经过计算，【答案：105000】",
        agent_type="Baseline"
    )

    # 测试获取DataFrame
    print("4. 获取评估结果表格:")
    df = eval_mgr.get_evaluation_dataframe()
    print(df.to_string(index=False))
    print()

    # 测试统计信息
    print("5. 获取统计信息:")
    stats = eval_mgr.get_statistics()
    print(f"  总评估数: {stats['total']}")
    print(f"  正确数: {stats['correct']}")
    print(f"  准确率: {stats['accuracy']:.2f}%")
    if stats['by_agent']:
        print("  按Agent类型:")
        for agent_type, agent_stats in stats['by_agent'].items():
            print(f"    {agent_type}: {agent_stats['total']} 次, 准确率 {agent_stats['accuracy']:.2f}%")
    print()

    # 测试导出CSV
    print("6. 导出CSV:")
    export_path = eval_mgr.export_csv()
    if export_path:
        print(f"  ✓ 已导出到: {export_path}")
    else:
        print("  ⚠️ 没有数据可导出")
    print()

    print("="*60)
    print("测试完成！")
    print("="*60)

if __name__ == "__main__":
    test_evaluation_manager()
