"""
拆分CSV文件为测试集和数据源
- 测试集：包含月同比、环比等预计算指标
- 数据源：包含原始销量数据和市场份额数据
"""
import pandas as pd
import os

# 配置
script_dir = os.path.dirname(os.path.abspath(__file__))
input_file = os.path.join(script_dir, "../课题数据(1).csv")
test_output = os.path.join(script_dir, "../测试集_月同比.csv")
source_output = os.path.join(script_dir, "../数据源_销量.csv")

print("=" * 60)
print("开始拆分CSV文件")
print("=" * 60)

# 读取原始数据
print(f"\n📖 读取文件: {input_file}")
df = pd.read_csv(input_file)
print(f"总行数: {len(df)}")
print(f"列: {list(df.columns)}")

# 显示数据概览
print(f"\n📊 数据概览:")
print(f"  - 指标数量: {df['indicator_key'].nunique()}")
print(f"  - 时间范围: {df['data_time'].min()} ~ {df['data_time'].max()}")
print(f"  - 单位类型: {df['unit'].unique()}")

# 拆分逻辑
# 测试集：包含"月同比"、"环比"字段的预计算指标
# 数据源：原始销量数据和市场份额数据

# 识别测试集（月同比、环比）
test_pattern = df['display_name'].str.contains('同比|环比', na=False)
test_df = df[test_pattern].copy()

# 数据源：其他所有数据
source_df = df[~test_pattern].copy()

print(f"\n✂️  拆分结果:")
print(f"  - 测试集（预计算指标）: {len(test_df)} 行")
print(f"  - 数据源（原始数据）: {len(source_df)} 行")
print(f"  - 合计: {len(test_df) + len(source_df)} 行")

# 验证拆分完整性
if len(test_df) + len(source_df) != len(df):
    print("⚠️  警告：拆分后行数不匹配！")
else:
    print("✅ 拆分完整性验证通过")

# 保存测试集
print(f"\n💾 保存测试集: {test_output}")
test_df.to_csv(test_output, index=False, encoding='utf-8-sig')
print(f"  - 文件大小: {os.path.getsize(test_output) / 1024:.2f} KB")

# 保存数据源
print(f"\n💾 保存数据源: {source_output}")
source_df.to_csv(source_output, index=False, encoding='utf-8-sig')
print(f"  - 文件大小: {os.path.getsize(source_output) / 1024:.2f} KB")

# 显示测试集统计
print(f"\n📋 测试集统计:")
print(f"  - 指标数量: {test_df['indicator_key'].nunique()}")
print(f"  - 指标类型: {test_df['display_name'].str.extract(r'：(.*?):')[0].unique()}")

# 显示数据源统计
print(f"\n📋 数据源统计:")
print(f"  - 指标数量: {source_df['indicator_key'].nunique()}")
print(f"  - 单位分布:")
for unit in source_df['unit'].unique():
    count = len(source_df[source_df['unit'] == unit])
    print(f"    - {unit}: {count} 行")

# 显示数据源样例
print(f"\n📄 数据源样例 (前5行):")
print(source_df.head(5).to_string())

# 显示测试集样例
print(f"\n📄 测试集样例 (前5行):")
print(test_df.head(5).to_string())

print(f"\n{'=' * 60}")
print("✅ 拆分完成！")
print(f"{'=' * 60}")
print(f"测试集文件: {test_output}")
print(f"数据源文件: {source_output}")
