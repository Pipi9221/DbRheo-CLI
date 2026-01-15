"""
测试新的评估功能
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from gradio_app import EvaluationManager

def test_new_features():
    """测试新功能"""
    print("="*60)
    print("测试新评估功能")
    print("="*60 + "\n")

    # 创建评估管理器
    eval_mgr = EvaluationManager()

    # 模拟同一问题多次运行
    print("1. 测试同一问题多次运行:")
    question1 = "2023-12，一汽大众的销量是多少？"
    standard_answer1 = "15000"

    # NL2SQL - 第1次运行
    eval_mgr.add_evaluation(
        question=question1,
        standard_answer=standard_answer1,
        actual_response="根据查询结果，【答案：15000】",
        agent_type="NL2SQL"
    )

    # NL2SQL - 第2次运行
    eval_mgr.add_evaluation(
        question=question1,
        standard_answer=standard_answer1,
        actual_response="【答案：14500】",
        agent_type="NL2SQL"
    )

    # Baseline - 第1次运行
    eval_mgr.add_evaluation(
        question=question1,
        standard_answer=standard_answer1,
        actual_response="【答案：15000】",
        agent_type="Baseline"
    )

    print(f"  已添加3次运行记录\n")

    # 添加其他问题
    question2 = "2023年比亚迪的总销量是多少？"
    eval_mgr.add_evaluation(
        question=question2,
        standard_answer="100000",
        actual_response="【答案：100000】",
        agent_type="NL2SQL"
    )

    eval_mgr.add_evaluation(
        question=question2,
        standard_answer="100000",
        actual_response="【答案：95000】",
        agent_type="Baseline"
    )

    print("2. 测试问题指纹:")
    fp1 = eval_mgr._generate_fingerprint(question1)
    fp2 = eval_mgr._generate_fingerprint(question2)
    print(f"  问题1指纹: {fp1}")
    print(f"  问题2指纹: {fp2}")
    print()

    # 测试按Agent分类统计（取最新）
    print("3. 测试按Agent分类统计（每个问题只取最新）:")
    stats = eval_mgr.get_statistics_by_agent_latest()
    print(f"  NL2SQL: {stats['NL2SQL']['correct']}/{stats['NL2SQL']['total']} = {stats['NL2SQL']['accuracy']:.1f}%")
    print(f"  Baseline: {stats['Baseline']['correct']}/{stats['Baseline']['total']} = {stats['Baseline']['accuracy']:.1f}%")
    print(f"  胜者: {stats['winner']}")
    print()

    # 测试筛选
    print("4. 测试筛选功能:")
    df_all = eval_mgr.get_evaluation_dataframe(agent_filter="全部")
    print(f"  全部记录: {len(df_all)} 条")

    df_nl2sql = eval_mgr.get_evaluation_dataframe(agent_filter="NL2SQL")
    print(f"  NL2SQL记录: {len(df_nl2sql)} 条")

    df_baseline = eval_mgr.get_evaluation_dataframe(agent_filter="Baseline")
    print(f"  Baseline记录: {len(df_baseline)} 条")
    print()

    # 测试问题搜索
    print("5. 测试问题搜索:")
    results = eval_mgr.search_questions("一汽大众")
    print(f"  找到 {len(results)} 个匹配问题:")
    for r in results:
        print(f"    - {r['question'][:50]}... (运行{r['count']}次)")
    print()

    # 测试问题详情
    print("6. 测试获取问题详情:")
    df_details = eval_mgr.get_question_details(fp1)
    print(f"  问题1的所有运行记录:")
    print(df_details.to_string(index=False))
    print()

    # 测试按Agent筛选问题详情
    print("7. 测试按Agent筛选问题详情:")
    df_nl2sql_details = eval_mgr.get_question_details(fp1, "NL2SQL")
    print(f"  问题1的NL2SQL运行记录:")
    print(df_nl2sql_details.to_string(index=False))
    print()

    print("="*60)
    print("测试完成！")
    print("="*60)

if __name__ == "__main__":
    test_new_features()
