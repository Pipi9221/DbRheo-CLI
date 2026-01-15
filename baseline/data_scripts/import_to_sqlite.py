"""
将拆分后的数据源导入SQLite数据库
遵循SCHEMA.md中的表结构规范
表1: vehicle_sales - 车型销量表（单位：辆）
表2: market_share - 市场份额表（单位：%）
"""
import pandas as pd
import sqlite3
import os

# 配置
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "../数据源_销量.csv")
db_path = os.path.join(script_dir, "../../db/vehicle_sales.db")

print("=" * 80)
print("数据导入SQLite数据库")
print("=" * 80)

# 读取数据源
print(f"\n📖 读取数据源: {csv_path}")
df = pd.read_csv(csv_path)
print(f"总行数: {len(df)}")
print(f"列: {list(df.columns)}")

# 显示数据概览
print(f"\n📊 数据概览:")
print(f"  - 指标数量: {df['indicator_key'].nunique()}")
print(f"  - 时间范围: {df['data_time'].min()} ~ {df['data_time'].max()}")
print(f"  - 单位类型: {df['unit'].unique()}")
print(f"  - 各单位数据量:")
for unit in df['unit'].unique():
    count = len(df[df['unit'] == unit])
    print(f"    - {unit}: {count} 行")

# 分离销量数据和市场份额数据
sales_df = df[df['unit'] == '辆'].copy()
share_df = df[df['unit'] == '%'].copy()

print(f"\n✂️  数据分离:")
print(f"  - 销量数据 (unit='辆'): {len(sales_df)} 行")
print(f"  - 市场份额数据 (unit='%'): {len(share_df)} 行")

# 解析display_name函数
def parse_display_name(display_name):
    """
    解析display_name，提取品牌和车型
    格式示例：
    - "乘用车销量：比亚迪_海豚：月"
    - "乘用车销量市场份额：吉利_星瑞：月"
    """
    try:
        # 移除引号
        if isinstance(display_name, str):
            display_name = display_name.strip('"')

        # 分割
        parts = display_name.split('：')
        if len(parts) >= 3:
            brand_model = parts[1].strip()
            if '_' in brand_model:
                # 处理品牌_车型格式
                brand, model = brand_model.split('_', 1)
                return brand.strip(), model.strip()
            else:
                # 如果没有下划线，可能是分类（如"1.0L以下"）
                # 这种情况归为"其他"分类
                return '其他', brand_model
    except Exception as e:
        pass
    return None, None

# 处理销量数据
print(f"\n🔧 处理销量数据...")
sales_df[['brand', 'model']] = sales_df['display_name'].apply(
    lambda x: pd.Series(parse_display_name(x))
)
# 移除无法解析的行
before_count = len(sales_df)
sales_df = sales_df.dropna(subset=['brand', 'model'])
after_count = len(sales_df)
print(f"  - 解析前: {before_count} 行")
print(f"  - 解析后: {after_count} 行")
print(f"  - 移除无效: {before_count - after_count} 行")

# 处理市场份额数据
print(f"\n🔧 处理市场份额数据...")
share_df[['brand', 'model']] = share_df['display_name'].apply(
    lambda x: pd.Series(parse_display_name(x))
)
# 移除无法解析的行
before_count = len(share_df)
share_df = share_df.dropna(subset=['brand', 'model'])
after_count = len(share_df)
print(f"  - 解析前: {before_count} 行")
print(f"  - 解析后: {after_count} 行")
print(f"  - 移除无效: {before_count - after_count} 行")

# 创建数据库目录
db_dir = os.path.dirname(db_path)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

# 创建数据库连接
print(f"\n💾 创建数据库: {db_path}")
conn = sqlite3.connect(db_path)

# 创建销量表
print(f"\n📋 创建销量表 (vehicle_sales)...")
sales_table = sales_df[[
    'indicator_key', 'brand', 'model', 'ind_value', 'data_time'
]].rename(columns={
    'indicator_key': 'indicator_id',
    'ind_value': 'sales_volume',
    'data_time': 'date'
})

# 确保日期格式正确
sales_table['date'] = pd.to_datetime(sales_table['date']).dt.strftime('%Y-%m-%d')

sales_table.to_sql('vehicle_sales', conn, if_exists='replace', index=False)
print(f"  - 插入行数: {len(sales_table)}")

# 创建市场份额表
print(f"\n📋 创建市场份额表 (market_share)...")
share_table = share_df[[
    'indicator_key', 'brand', 'model', 'ind_value', 'data_time'
]].rename(columns={
    'indicator_key': 'indicator_id',
    'ind_value': 'market_share',
    'data_time': 'date'
})

# 确保日期格式正确
share_table['date'] = pd.to_datetime(share_table['date']).dt.strftime('%Y-%m-%d')

share_table.to_sql('market_share', conn, if_exists='replace', index=False)
print(f"  - 插入行数: {len(share_table)}")

# 创建索引
print(f"\n🔗 创建索引...")
conn.execute('CREATE INDEX IF NOT EXISTS idx_sales_brand ON vehicle_sales(brand)')
print("  - idx_sales_brand (vehicle_sales.brand)")
conn.execute('CREATE INDEX IF NOT EXISTS idx_sales_date ON vehicle_sales(date)')
print("  - idx_sales_date (vehicle_sales.date)")
conn.execute('CREATE INDEX IF NOT EXISTS idx_share_brand ON market_share(brand)')
print("  - idx_share_brand (market_share.brand)")
conn.execute('CREATE INDEX IF NOT EXISTS idx_share_date ON market_share(date)')
print("  - idx_share_date (market_share.date)")

# 提交事务
conn.commit()

# 显示数据库统计
print(f"\n{'=' * 80}")
print("📊 数据库统计")
print(f"{'=' * 80}")

# 获取数据库文件大小
db_size = os.path.getsize(db_path) / 1024 / 1024
print(f"\n数据库文件: {db_path}")
print(f"文件大小: {db_size:.2f} MB")

# 销量表统计
print(f"\n表1: vehicle_sales (车型销量表)")
print(f"  - 行数: {len(sales_table)}")
print(f"  - 品牌数: {sales_table['brand'].nunique()}")
print(f"  - 车型数: {sales_table['model'].nunique()}")
print(f"  - 时间范围: {sales_table['date'].min()} ~ {sales_table['date'].max()}")
print(f"  - 字段: indicator_id, brand, model, sales_volume, date")
print(f"  - 单位: 辆")

# 市场份额表统计
print(f"\n表2: market_share (市场份额表)")
print(f"  - 行数: {len(share_table)}")
print(f"  - 品牌数: {share_table['brand'].nunique()}")
print(f"  - 车型数: {share_table['model'].nunique()}")
print(f"  - 时间范围: {share_table['date'].min()} ~ {share_table['date'].max()}")
print(f"  - 字段: indicator_id, brand, model, market_share, date")
print(f"  - 单位: %")

# 显示样例数据
print(f"\n{'=' * 80}")
print("📄 数据样例")
print(f"{'=' * 80}")

print(f"\nvehicle_sales (销量表) 前5行:")
sales_sample = pd.read_sql("SELECT * FROM vehicle_sales LIMIT 5", conn)
print(sales_sample.to_string(index=False))

print(f"\nmarket_share (市场份额表) 前5行:")
share_sample = pd.read_sql("SELECT * FROM market_share LIMIT 5", conn)
print(share_sample.to_string(index=False))

# 显示品牌列表
print(f"\n{'=' * 80}")
print("🚗 品牌列表")
print(f"{'=' * 80}")

brands = pd.read_sql("""
    SELECT brand, COUNT(*) as model_count
    FROM vehicle_sales
    GROUP BY brand
    ORDER BY model_count DESC
    LIMIT 20
""", conn)
print(f"\nvehicle_sales 表中的品牌 (前20):")
print(brands.to_string(index=False))

# 关闭连接
conn.close()

print(f"\n{'=' * 80}")
print("✅ 数据导入完成！")
print(f"{'=' * 80}")
print(f"\n数据库路径: {db_path}")
print(f"可以使用 SQLite 客户端或 Python sqlite3 模块访问数据库")
