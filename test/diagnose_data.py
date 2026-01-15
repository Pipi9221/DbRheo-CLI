"""
诊断数据格式和过滤逻辑
"""
import sys
import os
from pathlib import Path
import pandas as pd

# 添加项目路径
project_root = Path(__file__).parent.parent
baseline_dir = project_root / "baseline"
sys.path.insert(0, str(baseline_dir))

from baseline_agent_enhanced import EnhancedBaselineAgent


def diagnose():
    """诊断数据和过滤逻辑"""

    print("\n" + "="*80)
    print("🔍 数据诊断")
    print("="*80 + "\n")

    # 初始化agent
    csv_path = baseline_dir / "数据源_销量.csv"
    agent = EnhancedBaselineAgent(str(csv_path))

    print("\n" + "="*80)
    print("📊 数据概览")
    print("="*80)
    print(f"总行数: {len(agent.df)}")
    print(f"列名: {agent.columns}")

    # 统计display_name的格式
    print("\n" + "="*80)
    print("📝 display_name 格式分析")
    print("="*80)

    # 检查分隔符
    has_plus = agent.df['display_name'].str.contains('+').sum()
    has_underscore = agent.df['display_name'].str.contains('_').sum()

    print(f"\n使用加号(+)分隔: {has_plus} 条")
    print(f"使用下划线(_)分隔: {has_underscore} 条")

    # 显示不同的品牌格式
    print("\n" + "="*80)
    print("🚗 品牌/车型示例")
    print("="*80)

    samples = agent.df['display_name'].head(20)
    for i, name in enumerate(samples, 1):
        # 分割出品牌和车型
        if '+' in name:
            parts = name.split('+', 1)
            if ':' in parts[1]:
                vehicle_part, freq = parts[1].rsplit(':', 1)
                print(f"{i}. 品牌: {parts[0]}")
                print(f"   车型: {vehicle_part}")
                print(f"   频率: {freq}")
                print()
        else:
            print(f"{i}. {name}")
            print()

    # 测试关键词匹配
    print("\n" + "="*80)
    print("🔍 关键词匹配测试")
    print("="*80)

    test_keywords = [
        ("一汽大众", "揽境"),
        ("一汽大众", "高尔夫A8"),
        ("比亚迪", "海豚"),
        ("吉利", None)  # 全系
    ]

    for brand, model in test_keywords:
        print(f"\n搜索: 品牌='{brand}', 车型='{model}'")

        # 构建过滤条件
        mask = pd.Series([False] * len(agent.df), index=agent.df.index)

        # 品牌匹配
        mask |= agent.df['display_name'].str.contains(str(brand), na=False)

        # 车型匹配（如果有）
        if model:
            mask |= agent.df['display_name'].str.contains(str(model), na=False)

        # 统计结果
        filtered = agent.df[mask]
        print(f"   匹配数: {len(filtered)}")

        if len(filtered) > 0:
            print(f"   前3个匹配结果:")
            for i, row in filtered.head(3).iterrows():
                print(f"     {i+1}. {row[1]['display_name']}")
        else:
            print(f"   ⚠️  无匹配结果")

    # 查看特定时间的数据
    print("\n" + "="*80)
    print("📅 时间数据示例")
    print("="*80)

    time_samples = ['2023-06-01', '2023-05-01', '2023-12-01', '2016-12-01']

    for time_str in time_samples:
        filtered = agent.df[agent.df['data_time'].str.startswith(time_str[:7])]
        print(f"\n时间: {time_str[:7]} (前缀匹配)")
        print(f"   匹配数: {len(filtered)}")

        if len(filtered) > 0:
            print(f"   前3个结果:")
            for i, (idx, row) in enumerate(filtered.head(3).iterrows(), 1):
                print(f"     {i}. {row['display_name']} | unit: {row['unit']} | value: {row['ind_value']}")


if __name__ == "__main__":
    diagnose()
